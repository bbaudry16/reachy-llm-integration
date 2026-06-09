"""
Piper TTS — wrapper Python simple
Utilise le binaire piper via subprocess.
"""

import subprocess
import argparse
import json
import os

PIPER_BIN  = "./piper/piper"
VOICE_DIR  = "./voice"


def synthesize(text: str, model: str, output: str, speaker: int = None, length_scale: float = 1.0, noise_scale: float = 0.667, noise_w: float = 0.8) -> None:
    """
    length_scale : vitesse de lecture (>1 = plus lent, <1 = plus rapide)
    noise_scale  : variation de la voix
    noise_w      : variation du rythme
    """
    cmd = [
        PIPER_BIN,
        "--model",        model,
        "--output_file",  output,
        "--length_scale", str(length_scale),
        "--noise_scale",  str(noise_scale),
        "--noise_w",      str(noise_w),
    ]
    if speaker is not None:
        cmd += ["--speaker", str(speaker)]

    print(f"Synthèse : \"{text}\"")
    print(f"Modèle   : {model}")
    if speaker is not None:
        print(f"Speaker  : {speaker}")
    print(f"Vitesse  : {length_scale} (1.0 = normal, >1 = lent, <1 = rapide)")
    print(f"Sortie   : {output}\n")

    result = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        capture_output=True,
    )

    if result.returncode != 0:
        print(f"Erreur piper :\n{result.stderr.decode()}")
    else:
        print(f"Fichier généré : {output}")
        os.system(f"aplay {output}")


def main():
    parser = argparse.ArgumentParser(description="Piper TTS wrapper")
    subparsers = parser.add_subparsers(dest="command")

    # -- list-voices
    subparsers.add_parser("list-voices", help="Lister les voix disponibles")

    # -- list-speakers
    sp = subparsers.add_parser("list-speakers", help="Lister les speakers d'une voix")
    sp.add_argument("--model", required=True, help="Chemin vers le .onnx")

    # -- speak
    speak_p = subparsers.add_parser("speak", help="Synthétiser du texte")
    speak_p.add_argument("--text",         required=True,          help="Texte à synthétiser")
    speak_p.add_argument("--model",        required=True,          help="Chemin vers le .onnx")
    speak_p.add_argument("--output",       default="output.wav",   help="Fichier de sortie (défaut: output.wav)")
    speak_p.add_argument("--speaker",      type=int, default=None, help="Index du speaker (voix multi-speaker)")
    speak_p.add_argument("--speed",        type=float, default=1.0,help="Vitesse (1.0=normal, 0.8=rapide, 1.3=lent)")
    speak_p.add_argument("--noise-scale",  type=float, default=0.667, help="Variation voix (défaut: 0.667)")
    speak_p.add_argument("--noise-w",      type=float, default=0.8,   help="Variation rythme (défaut: 0.8)")

    args = parser.parse_args()

    if args.command == "list-voices":
        list_voices()

    elif args.command == "list-speakers":
        list_speakers(args.model)

    elif args.command == "speak":
        synthesize(
            text=args.text,
            model=args.model,
            output=args.output,
            speaker=args.speaker,
            length_scale=args.speed,
            noise_scale=args.noise_scale,
            noise_w=args.noise_w,
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()