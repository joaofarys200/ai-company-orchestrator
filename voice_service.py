import os
import time
import threading
import numpy as np
import webrtcvad
import sounddevice as sd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VoiceService:
    @staticmethod
    def _env_int(name, default, minimum=None, maximum=None):
        value = os.getenv(name)
        if value is None or value.strip() == "":
            return default
        try:
            parsed = int(value)
        except ValueError:
            return default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    @staticmethod
    def _env_float(name, default, minimum=None, maximum=None):
        value = os.getenv(name)
        if value is None or value.strip() == "":
            return default
        try:
            parsed = float(value)
        except ValueError:
            return default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def __init__(self, on_speech_start=None, on_speech_end=None, on_transcribing=None, on_transcription=None, model_name="tiny", sensitivity=3):
        self.sample_rate = 16000
        self.interval_size = 30  # ms (webrtcvad supports 10, 20, 30 ms)
        self.block_size = int(self.sample_rate * self.interval_size / 1000)  # 480 samples
        self.default_sensitivity = sensitivity
        self.configure_detection()
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.on_transcribing = on_transcribing
        self.on_transcription = on_transcription
        self.model_name = model_name
        
        # Read device index and gain from environment
        device_index_env = os.getenv("VOICE_DEVICE_INDEX")
        self.device_index = None
        if device_index_env is not None and device_index_env.strip() != "":
            try:
                self.device_index = int(device_index_env)
            except ValueError:
                self.device_index = None
                
        gain_env = os.getenv("VOICE_GAIN")
        self.gain = 1.0
        if gain_env is not None and gain_env.strip() != "":
            try:
                self.gain = float(gain_env)
            except ValueError:
                self.gain = 1.0
                
        print(
            "VoiceService initialized: "
            f"device_index={self.device_index}, gain={self.gain}, "
            f"vad_sensitivity={self.vad_sensitivity}, rms_threshold={self.rms_threshold}, "
            f"min_speech_ms={self.min_speech_ms}"
        )
        
        self.is_listening = False
        self.voiced_frames = []
        self.block_since_last_spoke = 0
        self.candidate_speech_blocks = 0
        self.max_silent_blocks = 45  # 45 blocks * 30ms = 1350ms of silence to trigger end of speech (prevents cutting off natural pauses)
        self.speaking = False
        self.whisper_model = None

    def configure_detection(self):
        self.vad_sensitivity = self._env_int("VOICE_VAD_SENSITIVITY", self.default_sensitivity, 0, 3)
        self.vad = webrtcvad.Vad(self.vad_sensitivity)
        default_rms = self._env_float("VOICE_INTERRUPT_RMS_THRESHOLD", 900.0, 0.0, 32768.0)
        self.rms_threshold = self._env_float("VOICE_RMS_THRESHOLD", default_rms, 0.0, 32768.0)
        self.min_speech_ms = self._env_int("VOICE_MIN_SPEECH_MS", 240, 0, 3000)
        self.min_speech_blocks = max(1, int((self.min_speech_ms + self.interval_size - 1) // self.interval_size))

    def load_model(self):
        if self.whisper_model is None:
            if self.on_transcribing:
                self.on_transcribing()
            print(f"Loading local Whisper model: '{self.model_name}' on CPU...")
            from faster_whisper import WhisperModel
            # Using CPU and int8 quantization to ensure low resource footprint locally
            self.whisper_model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            print("Local Whisper model loaded successfully.")

    def audio_callback(self, indata, frames, time_info, status):
        if not self.is_listening:
            return
            
        # Apply volume gain boost if configured
        if self.gain != 1.0:
            audio_frame = np.clip(indata.astype(np.float32) * self.gain, -32768, 32767).astype(np.int16)
        else:
            audio_frame = indata
        raw_bytes = audio_frame.tobytes()
        
        try:
            rms = float(np.sqrt(np.mean(audio_frame.astype(np.float32) ** 2))) if audio_frame.size else 0.0
            is_speech = self.vad.is_speech(raw_bytes, self.sample_rate) and rms >= self.rms_threshold
        except Exception as e:
            is_speech = False
            rms = 0.0
            
        if is_speech:
            self.candidate_speech_blocks += 1
            if not self.speaking:
                if self.candidate_speech_blocks >= self.min_speech_blocks:
                    self.speaking = True
                    if self.on_speech_start:
                        self.on_speech_start()
            self.voiced_frames.append(raw_bytes)
            if self.speaking:
                self.block_since_last_spoke = 0
        else:
            if self.speaking:
                self.voiced_frames.append(raw_bytes)
                self.block_since_last_spoke += 1
                if self.block_since_last_spoke >= self.max_silent_blocks:
                    self.speaking = False
                    self.candidate_speech_blocks = 0
                    self.process_audio()
            else:
                self.candidate_speech_blocks = 0
                # Keep a rolling buffer of 5 silent blocks (150ms) to avoid clipping start of sentences
                if len(self.voiced_frames) > 5:
                    self.voiced_frames.pop(0)
                self.voiced_frames.append(raw_bytes)

    def process_audio(self):
        if not self.voiced_frames:
            return
            
        audio_data = b"".join(self.voiced_frames)
        self.voiced_frames = []
        
        # Run transcription in a background thread to keep audio capture non-blocking
        threading.Thread(target=self._transcribe_task, args=(audio_data,), daemon=True).start()

    def _transcribe_task(self, audio_bytes):
        try:
            self.load_model()
            
            # Convert raw 16-bit PCM bytes back to float32 normalized array
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            start_time = time.time()
            # Transcribe audio using Portuguese (pt) language setting with VAD filter and without history conditioning to prevent hallucinations
            segments, info = self.whisper_model.transcribe(
                audio_np, 
                language="pt", 
                beam_size=5, 
                vad_filter=True, 
                condition_on_previous_text=False
            )
            text = "".join([seg.text for seg in segments]).strip()
            duration = time.time() - start_time
            print(f"Local Whisper transcription finished in {duration:.2f}s -> '{text}'")
            
            # Filter common whisper hallucinations during silent frames
            hallucinations = ["por exemplo", "ao abrigo", "obrigado", "tchau", "legendado por", "legendas por", "subtitles by"]
            clean_text = text.lower().strip(" .?!,")
            if not text or len(clean_text) <= 2 or clean_text in hallucinations:
                print(f"VAD Backend: Ignored silence hallucination ('{text}')")
                if self.on_speech_end:
                    self.on_speech_end()
                return
                
            print(f"VAD Backend: Speech transcribed -> '{text}'")
            if self.on_transcription:
                self.on_transcription(text)
        except Exception as e:
            print(f"Error in transcription: {e}")
            if self.on_speech_end:
                self.on_speech_end()

    def start(self):
        if self.is_listening:
            return
            
        # Re-read environment variables on start to catch runtime changes in .env
        load_dotenv()
        device_index_env = os.getenv("VOICE_DEVICE_INDEX")
        self.device_index = None
        if device_index_env is not None and device_index_env.strip() != "":
            try:
                self.device_index = int(device_index_env)
            except ValueError:
                self.device_index = None
                
        gain_env = os.getenv("VOICE_GAIN")
        self.gain = 1.0
        if gain_env is not None and gain_env.strip() != "":
            try:
                self.gain = float(gain_env)
            except ValueError:
                self.gain = 1.0

        self.configure_detection()
        print(
            "VoiceService starting stream: "
            f"device_index={self.device_index}, gain={self.gain}, "
            f"vad_sensitivity={self.vad_sensitivity}, rms_threshold={self.rms_threshold}, "
            f"min_speech_ms={self.min_speech_ms}"
        )
        
        self.is_listening = True
        self.speaking = False
        self.voiced_frames = []
        self.block_since_last_spoke = 0
        self.candidate_speech_blocks = 0
        
        def listen_loop():
            try:
                # Open mono 16kHz stream capturing 16-bit integer PCM samples
                try:
                    with sd.InputStream(
                        device=self.device_index,
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype='int16',
                        blocksize=self.block_size,
                        callback=self.audio_callback
                    ):
                        print(f"Microphone audio stream active using device {self.device_index or 'default'}.")
                        while self.is_listening:
                            sd.sleep(100)
                except Exception as first_err:
                    print(f"Voice service: Failed to start stream with device {self.device_index}: {first_err}. Falling back to default system microphone.")
                    with sd.InputStream(
                        device=None,
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype='int16',
                        blocksize=self.block_size,
                        callback=self.audio_callback
                    ):
                        print("Microphone audio stream active using default system microphone.")
                        while self.is_listening:
                            sd.sleep(100)
            except Exception as e:
                print(f"Voice service stream error: {e}")
                self.is_listening = False
                if self.on_speech_end:
                    self.on_speech_end()
                    
        threading.Thread(target=listen_loop, daemon=True).start()
        print("Voice service background listener started.")

    def stop(self):
        self.is_listening = False
        self.speaking = False
        print("Voice service listener stopped.")
