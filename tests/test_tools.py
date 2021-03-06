from argparse import Namespace
from unittest.mock import Mock, call

from cc2olx.tools.video_upload import (
    main,
    parse_args,
    upload_transcript,
    OAUTH_TOKEN_URL,
    GENERATE_UPLOAD_LINK_BASE_URL,
    TRANSCRIPT_UPLOAD_LINK,
)

MOCK_UPLOAD_LINK_ROOT = "example.com/upload"

FILE_UPLOAD_URLS = {
    "0 - Introductions.mp4": "abc",
    "1 - Preview.mp4": "def",
    "2 - Conundrums in AI.mov": "ghi",
    "3 - Characteristics of AI Problems.mov": "jkl",
}


def post_side_effect(*args, **kwargs):
    # mock OAuth access token API call
    if args[0] == OAUTH_TOKEN_URL:
        mock = Mock()
        json = {"access_token": "123"}
        mock.json.return_value = json
        return mock
    # mock Studio generate upload link API call
    elif args[0] == GENERATE_UPLOAD_LINK_BASE_URL + "course-v1:edX+111222+111222":
        filename = kwargs["json"]["files"][0]["file_name"]
        filename_id = FILE_UPLOAD_URLS.get(filename, "")

        mock = Mock()
        json = {
            "files": [
                {
                    "edx_video_id": filename_id,
                    "upload_url": MOCK_UPLOAD_LINK_ROOT + "/" + filename_id,
                }
            ]
        }
        mock.json.return_value = json
        return mock
    elif args[0] == TRANSCRIPT_UPLOAD_LINK:
        mock = Mock()
        mock.status_code = 201
        return mock
    else:
        return Mock()


def put_side_effect(*args, **kwargs):
    # mock video upload API call
    if args[0].startswith(MOCK_UPLOAD_LINK_ROOT):
        mock = Mock()
        mock.status_code = 200
        return mock
    else:
        return Mock()


class TestVideoUpload:
    def test_video_upload(self, mocker, monkeypatch, video_upload_args):
        # patch the the parse_args method to mock out command line arguments
        args_mock = Mock()
        args_mock.configure_mock(**video_upload_args)
        mocker.patch("cc2olx.tools.video_upload.parse_args", return_value=args_mock)

        monkeypatch.setenv("CC2OLX_CLIENT", "client")
        monkeypatch.setenv("CC2OLX_SECRET", "secret")

        # patch API calls
        mocker.patch("cc2olx.tools.video_upload.requests.post", side_effect=post_side_effect)
        mocker.patch("cc2olx.tools.video_upload.requests.Session.post", side_effect=post_side_effect)
        upload_video_mock = mocker.patch("cc2olx.tools.video_upload.requests.put", side_effect=put_side_effect)

        # patch writerow method of csv.DictWriter class so that we can assert against
        # data written to the output csv
        csv_writerow_mock = mocker.patch("csv.DictWriter.writerow")

        main()

        expected_upload_video_call_args = [
            call("example.com/upload/ghi", data=b"", headers={"Content-Type": "video/quicktime"}),
            call("example.com/upload/abc", data=b"", headers={"Content-Type": "video/mp4"}),
            call("example.com/upload/def", data=b"", headers={"Content-Type": "video/mp4"}),
            call("example.com/upload/jkl", data=b"", headers={"Content-Type": "video/quicktime"}),
        ]
        upload_video_mock.assert_has_calls(expected_upload_video_call_args, any_order=True)

        expected_csv_writerow_call_args = [
            call(
                {
                    "Edx Id": "Edx Id",
                    "Relative File Path": "Relative File Path",
                    "Additional Notes": "Additional Notes",
                    "Youtube ID": "Youtube ID",
                    "External Video Link": "External Video Link",
                    "Languages": "Languages",
                }
            ),
            call(
                {
                    "External Video Link": "https://cdnapisec.kaltura.com/p/2019031/sp/201903100/playManifest/"
                    "entryId/1_zeqnrfgw/format/url/protocol/https",
                    "Edx Id": "abc",
                    "Relative File Path": "01___Intro_to_Knowledge_Based_AI/0 - Introductions.mp4",
                    "Additional Notes": "This is the first video.",
                    "Youtube ID": "onRUvL2SBG8",
                    "Languages": "en",
                }
            ),
            call(
                {
                    "External Video Link": "https://cdnapisec.kaltura.com/p/2019031/sp/201903100/playManifest/"
                    "entryId/1_9if7cth0/format/url/protocol/https",
                    "Edx Id": "def",
                    "Relative File Path": "01___Intro_to_Knowledge_Based_AI/1 - Preview.mp4",
                    "Additional Notes": "",
                    "Youtube ID": "NXlG00JYX-o",
                    "Languages": "en-fr",
                }
            ),
            call(
                {
                    "External Video Link": "https://cdnapisec.kaltura.com/p/2019031/sp/201903100/playManifest/"
                    "entryId/1_c7j5va21/format/url/protocol/https",
                    "Edx Id": "ghi",
                    "Relative File Path": "01___Intro_to_Knowledge_Based_AI/2 - Conundrums in AI.mov",
                    "Additional Notes": "",
                    "Youtube ID": "_SIvUj7xUKc",
                    "Languages": "fr",
                }
            ),
            call(
                {
                    "External Video Link": "https://cdnapisec.kaltura.com/p/2019031/sp/201903100/playManifest/"
                    "entryId/1_xcjzc0q5/format/url/protocol/https",
                    "Edx Id": "jkl",
                    "Relative File Path": "01___Intro_to_Knowledge_Based_AI/3 - Characteristics of AI Problems.mov",
                    "Additional Notes": "This is the last video.",
                    "Youtube ID": "3pT8dh4ftbc",
                    "Languages": "",
                }
            ),
        ]
        csv_writerow_mock.assert_has_calls(expected_csv_writerow_call_args, any_order=True)


def test_parse_args():
    """
    Basic cli test.
    """

    parsed_args = parse_args(["courseid", "dirname", "input.csv", "--output-csv", "output.csv"])

    assert parsed_args == Namespace(
        course_id="courseid", directory="dirname", input_csv="input.csv", output_csv="output.csv"
    )


def upload_transcript_side_effect(*args, **kwargs):
    print(kwargs["data"])
    mock = Mock()

    if kwargs["data"].get("edx_video_id") and kwargs["data"].get("language_code"):
        mock.status_code = 201
    else:
        mock.status_code = 400

    return mock


def test_transcript_upload(mocker, transcript_file):
    mocker.patch("cc2olx.tools.video_upload.requests.post", side_effect=upload_transcript_side_effect)
    mocker.patch("cc2olx.tools.video_upload.requests.Session.post", side_effect=upload_transcript_side_effect)

    response = upload_transcript(transcript_file, "edxid", "en", "test_access_token")
    assert response.status_code == 201

    response = upload_transcript(transcript_file, "edxid", None, "test_access_token")
    assert response.status_code == 400

    response = upload_transcript(transcript_file, None, "en", "test_access_token")
    assert response.status_code == 400
