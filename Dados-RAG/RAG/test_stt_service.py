import io
import unittest
import wave
from types import SimpleNamespace
from fastapi import HTTPException
from fastapi.testclient import TestClient
import stt_service as stt

def wav(seconds=0.1):
    data=io.BytesIO()
    with wave.open(data,'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'))
        w.writeframes(b'\0\0'*int(16000*seconds))
    return data.getvalue()

class SttTests(unittest.TestCase):
    def setUp(self):
        self.previous=stt.model
        self.previous_preview=stt.preview_model
        self.calls=[]
        def transcribe(audio,**kwargs):
            self.calls.append(kwargs)
            return iter([SimpleNamespace(text=' Preciso de ajuda. ',no_speech_prob=0.1)]),None
        stt.model=SimpleNamespace(transcribe=transcribe)
        stt.preview_model=stt.model
        self.client=TestClient(stt.app)
    def tearDown(self):
        stt.model=self.previous
        stt.preview_model=self.previous_preview
        self.client.close()
    def test_transcription_and_health(self):
        self.assertEqual(self.client.get('/api/stt/health').status_code,200)
        r=self.client.post('/api/stt',content=wav(),headers={'Content-Type':'audio/wav'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['text'],'Preciso de ajuda.')
        self.assertIn('no-store',r.headers['cache-control'])
        self.assertEqual(self.calls[0]['language'],'pt')
    def test_preview_uses_fast_model(self):
        r=self.client.post('/api/stt?preview=true',content=wav(),headers={'Content-Type':'audio/wav'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.calls[0]['beam_size'],3)

    def test_invalid_empty_and_oversize(self):
        for data,mime,status in [(b'x','text/plain',415),(b'','audio/wav',422),(b'x','audio/wav',422),(b'x'*(stt.MAX_BYTES+1),'audio/webm',413)]:
            self.assertEqual(self.client.post('/api/stt',content=data,headers={'Content-Type':mime}).status_code,status)
    def test_duration_limit(self):
        with self.assertRaises(HTTPException) as error: stt.decode_audio(wav(61))
        self.assertEqual(error.exception.status_code,413)
    def test_busy_unavailable_silence(self):
        stt.lock.acquire()
        try:
            self.assertEqual(self.client.post('/api/stt',content=wav(),headers={'Content-Type':'audio/wav'}).status_code,429)
        finally: stt.lock.release()
        stt.model=None
        self.assertEqual(self.client.post('/api/stt',content=wav(),headers={'Content-Type':'audio/wav'}).status_code,503)
        stt.model=SimpleNamespace(transcribe=lambda *a,**k:(iter([]),None))
        self.assertEqual(self.client.post('/api/stt',content=wav(),headers={'Content-Type':'audio/wav'}).json()['text'],'')

if __name__=='__main__': unittest.main()
