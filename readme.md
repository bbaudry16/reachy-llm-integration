# Reachy Conversational Robot

Internship project developed at the [IRIMAS laboratory](https://irimas.uha.fr/), MSD branch,
under the supervision of [Maxime Devanne](https://maxime-devanne.com/).

Reachy is a humanoid robot that holds natural spoken conversations. It listens to a user via microphone, sends the transcription to a language model, and executes the response as synchronized speech and body movement. The robot expresses emotions through arm poses, head orientation, antenna angles, and pre-recorded animations driven entirely by the LLM output.

---

## Requirements

- Python 3.10
- A [Mistral AI](https://mistral.ai/) API key
- A Reachy robot reachable on the local network (default IP `localhost`)
- A Piper TTS model: `en_GB-semaine-medium.onnx` and its `.json` config, placed in `./model/`
- A working microphone

---

## Installation

### 1. Clone with submodules

```bash
git clone --recurse-submodules <repo-url>
cd <repo>
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

This pulls `libs/reachyController` from `https://github.com/bbaudry16/reachyController`.

### 2. Create a virtual environment

```bash
python3.10 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set the Mistral API key

```bash
export MISTRAL_API_KEY=your_key_here
```

Add this line to your `~/.bashrc` or `~/.zshrc` to persist it across sessions.


```
model/
  en_GB-semaine-medium.onnx
  en_GB-semaine-medium.onnx.json
```

---

## Running

```bash
bash launch.sh
```

Or manually:

```bash
source venv/bin/activate
python3 main.py
```

Press **Escape** to stop cleanly. The robot arms will return to rest and motors will turn off.

---

## Configuration

The main constants are at the top of `main.py`:

| Constant | Default | Description |
|---|---|---|
| `REACHY_IP` | `"localhost"` | IP address of the Reachy robot |
| `MODEL_PATH` | `"./model/en_GB-semaine-medium.onnx"` | Path to the Piper model |
| `SPEAKER_ID` | `3` | Speaker ID within the Piper model |
| `USE_VOICE` | `True` | Use microphone input; set to `False` for keyboard input |
| `FACE_SMOOTHING` | `0.5` | Smoothing factor for face tracking (0 = no smoothing) |

---

## How it works

### Conversation loop

1. **Speech to text** — `SpeechToText` records audio via `sounddevice` until silence is detected, then transcribes it with [faster-whisper](https://github.com/guillaumekln/faster-whisper) (OpenAI Whisper, `small` model).
2. **Language model** — `MistralClient` sends the transcription to Mistral (`mistral-small-2503`) with a system prompt that instructs the model to respond as a JSON object with two fields: `speech` (text to say) and `ryi` (YAML describing movements).
3. **Timing correction** — `YamlTimingFixer` parses the YAML and bumps motion durations to ensure they outlast the speech.
4. **Execution** — `Instructor` (from `reachyController`) walks the YAML and dispatches each action. Actions run in parallel blocks where possible.
5. **Text to speech** — `TextToSpeech` synthesizes the `speech` field with Piper and plays it through the default audio device.

### Face tracking

While the robot is idle (not executing an LLM response), `FaceTracker` runs a background thread that detects faces in the left camera feed using OpenCV Haar cascades. The largest detected face is smoothed and used to drive `head.lookAt()`, giving the impression that Reachy is watching the person it is talking to.

### Mood tracking

`MoodTracker` inspects each LLM response for pose labels and speech keywords to infer the robot's current emotional state. This state is injected as an additional system message in the next request, nudging the model to maintain emotional continuity across turns. Mood intensity decays exponentially over subsequent turns.

### Movement system

The LLM outputs a YAML block using a fixed vocabulary of actions:

- `llm_arms` — move one or both arms to a pose, play an animation, or perform an explanation gesture. The resolver automatically distinguishes between the three based on the label.
- `llm_arms_sequence` — play a sequence of arm labels one after another.
- `llm_move_head` / `llm_move_head_sequence` — move the head to named poses.
- `llm_look_at_human` — orient the head toward the detected face.
- `llm_set_antenna` — set antenna angles to a named pose.
- `llm_vibrate_antenna` — oscillate an antenna for expressive peaks.
- `llm_speak` — synthesize and play a text fragment.
- `parallel` — run a group of actions simultaneously, with automatic conflict detection to prevent two actions from claiming the same body part.

`poseVariation` adds a small random offset to the most expressive joint of each static pose, so the robot never holds exactly the same position twice.

---

## File structure

```
.
├── main.py                  # Entry point — conversation loop
├── launch.sh                # Convenience script (activates venv and runs main.py)
│
├── mistral.py               # Mistral API client with history and mood injection
├── promptBuilder.py         # Builds the LLM system prompt from the current libraries
├── yamlTimingFixer.py       # Corrects motion durations to outlast speech
├── actions.py               # Action handlers registered on the Reachy controller
│
├── faceDetector.py          # Background face detection and look-at conversion
├── moodTracker.py           # Emotional state tracking across conversation turns
│
├── poseLibrary.py           # Reads poses_library.json (arms, head, antennas)
├── animationLibrary.py      # Reads animations_library.json
├── poseVariation.py         # Adds subtle randomness to static arm poses
│
├── speechToText.py          # Microphone recording and Whisper transcription
├── textToSpeech.py          # Piper TTS synthesis and audio playback
│
├── poseRecorder.py          # CLI tool to record and save new poses
├── animationRecorder.py     # CLI tool to record and save new animations
├── poseCapturer.py          # CLI tool to capture cartesian poses
│
├── poses_library.json       # Library of named arm, head, and antenna poses
├── animations_library.json  # Library of named keyframe animations
│
├── requirements.txt
└── libs/
    └── reachyController/    # Git submodule — low-level Reachy SDK wrapper
```

---

## Adding poses and animations

### Recording a new pose

```bash
python3 poseRecorder.py
```

Use `R` / `L` / `H` to toggle stiffness on each body part, physically move the robot to the desired position, then press `Space` to capture. You will be prompted for a label, description, and category (`emotion`, `conversational`, or `explanation`).

### Recording a new animation

```bash
python3 animationRecorder.py
```

Capture multiple keyframes with `Space`, then press `Enter` to save. The animation is appended to `animations_library.json` and immediately available to the LLM on the next run (the system prompt is rebuilt at startup).

### Pose categories

| Category | When to use |
|---|---|
| `emotion` | Express a feeling (happy, sad, shocked, curious…) |
| `conversational` | Neutral states during dialogue (talking, thinking, neutral) |
| `explanation` | Single-arm gestures used as visual metaphors when teaching a concept |

---

## Dependencies

| Package | Version | Role |
|---|---|---|
| `faster-whisper` | 1.2.1 | Speech recognition (OpenAI Whisper) |
| `piper` | 0.15.1 | Text-to-speech synthesis |
| `reachy-sdk` | 0.5.4 | Reachy robot communication |
| `sounddevice` | 0.5.5 | Audio recording and playback |
| `requests` | 2.34.2 | Mistral API HTTP calls |
| `PyYAML` | 6.0.3 | YAML parsing for movement instructions |
| `numpy` | 1.21.0 | Audio array processing |
| `pynput` | ≥1.7.6 | Global keyboard listener (Escape to stop) |
| `opencv-python` | — | Face detection (pulled by reachy-sdk) |

---

## Acknowledgements

This project was developed as part of an internship at the
[IRIMAS laboratory](https://irimas.uha.fr/) (Institut de Recherche en Informatique,
Mathématiques, Automatique et Signal), MSD branch (Modélisation des Systèmes et Décision),
Université de Haute-Alsace.

Supervised by [Maxime Devanne](https://maxime-devanne.com/).