"""Contract tests without downloading or running a model."""
import io
import unittest
import wave
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tts_service import router, get_speech, LocalSpeech, SpeechUnavailable, SpeechBusy

class FakeSpeech:
    voice = object()
    error = None
    def synthesize(self, text):
        if self.error:
            raise self.error()
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\0\0' * 100)
        return output.getvalue()

class TtsTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSpeech()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides = {}
        import tts_service
        self.original = tts_service.get_speech
        tts_service.get_speech = lambda: self.fake
        self.client = TestClient(app)
    def tearDown(self):
        import tts_service
        tts_service.get_speech = self.original
        self.client.close()
    def test_audio_and_health(self):
        self.assertEqual(self.client.get('/api/tts/health').status_code, 200)
        r = self.client.post('/api/tts', json={'text':'Olá.'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'RIFF'))
        self.assertIn('no-store', r.headers['cache-control'])
        self.assertEqual(r.headers['content-type'], 'audio/wav')
    def test_invalid_text(self):
        for text in ['', '   ', 'x'*601]:
            self.assertEqual(self.client.post('/api/tts', json={'text':text}).status_code, 422)
    def test_busy_and_unavailable(self):
        for error, status in [(SpeechBusy,429),(SpeechUnavailable,503)]:
            self.fake.error = error
            self.assertEqual(self.client.post('/api/tts',json={'text':'Olá.'}).status_code,status)
    def test_missing_model_and_lock(self):
        speech=LocalSpeech(Path('/nonexistent/voice.onnx'))
        with self.assertRaises(SpeechUnavailable): speech.synthesize('Olá.')
        self.assertFalse(speech.lock.locked())
        speech.lock.acquire()
        with self.assertRaises(SpeechBusy): speech.synthesize('Olá.')
        speech.lock.release()

if __name__ == '__main__': unittest.main()
