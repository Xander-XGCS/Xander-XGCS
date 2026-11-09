import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from PIL import Image
import schumann_live as app

def fixture_jpeg():
    im=Image.new("RGB",(640,480),"orange")
    buf=io.BytesIO()
    im.save(buf,format="JPEG")
    return buf.getvalue()

class SchumannTests(unittest.TestCase):
    def test_image_validation(self):
        valid=app.validate_source_image(fixture_jpeg())
        self.assertEqual(valid.size,(640,480))
        with self.assertRaises(ValueError):
            app.validate_source_image(b"not jpeg")
        with self.assertRaises(ValueError):
            app.validate_source_image(b"\xff\xd8"+"x".encode()*(app.MAX_BYTES+1))

    def test_publication_not_observation(self):
        now=datetime(2026,11,8,20,tzinfo=timezone.utc)
        self.assertEqual(app.classify(now-timedelta(hours=12),now),"CURRENT")
        self.assertEqual(app.classify(now-timedelta(hours=72),now),"DELAYED")
        self.assertEqual(app.classify(None,now),"DELAYED")
        self.assertEqual(app.classify(now+timedelta(hours=4),now),"DELAYED")

    def test_old_unchanged_image_delayed(self):
        now=datetime(2026,11,8,20,tzinfo=timezone.utc)
        previous={"sha256":"abc","checked_utc":(now-timedelta(hours=55)).isoformat()}
        self.assertEqual(app.classify(now-timedelta(hours=3),now,previous,"abc"),"DELAYED")
        self.assertEqual(app.classify(now-timedelta(hours=3),now,previous,"def"),"CURRENT")

    def test_no_rights_no_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,"OUT",app.Path(folder)),\
                 patch.dict(os.environ,{"SCHUMANN_REUSE_APPROVED":"no"}),\
                 patch.object(app,"fetch_bgs") as fetch:
                result=app.refresh()
                fetch.assert_not_called()
                self.assertEqual(result["state"],"UNAVAILABLE")
                self.assertIsNone(result["observed_utc"])
                self.assertTrue((app.Path(folder)/"profile-banner.png").is_file())

    def test_failure_not_live(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,"OUT",app.Path(folder)),\
                 patch.dict(os.environ,{"SCHUMANN_REUSE_APPROVED":"yes"}),\
                 patch.object(app,"fetch_bgs",side_effect=ValueError("missing")):
                result=app.refresh()
                self.assertEqual(result["state"],"UNAVAILABLE")
                self.assertIn("missing",result["error"])

    def test_valid_source_metadata(self):
        now=datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,"OUT",app.Path(folder)),\
                 patch.dict(os.environ,{"SCHUMANN_REUSE_APPROVED":"yes"}),\
                 patch.object(app,"fetch_bgs",return_value=(Image.new("RGB",(640,480),"yellow"),"abc",now)):
                result=app.refresh()
                self.assertEqual(result["state"],"CURRENT")
                self.assertIsNone(result["observed_utc"])
                with Image.open(app.Path(folder)/"profile-banner.png") as im:
                    self.assertEqual(im.size,(1000,215))
if __name__=="__main__":
    unittest.main()
