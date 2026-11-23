/* Capture PCM on the audio thread; never connect microphone audio to speakers. */
class VoiceCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(2048);
    this.used = 0;
    this.stopped = false;
    this.port.onmessage = event => {
      if (event.data === 'flush') {
        this.stopped = true;
        this.flush();
        this.port.postMessage({ type: 'flushed' });
      }
    };
  }
  flush() {
    if (!this.used) return;
    const samples = this.buffer.slice(0, this.used);
    this.port.postMessage({ type: 'samples', samples }, [samples.buffer]);
    this.used = 0;
  }
  process(inputs) {
    const channels = inputs[0];
    if (this.stopped || !channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let mono = 0;
      for (const channel of channels) mono += channel[i] / channels.length;
      this.buffer[this.used++] = mono;
      if (this.used === this.buffer.length) this.flush();
    }
    return true;
  }
}
registerProcessor('guia-voice-capture', VoiceCapture);
