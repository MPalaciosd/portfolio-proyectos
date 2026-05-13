"""
Monitor de capturas de pantalla programadas
Toma capturas a intervalos configurables y las guarda con timestamp.

Uso:
    python monitor.py               # cada 60 segundos
    python monitor.py --interval 30 # cada 30 segundos
    python monitor.py --count 10    # tomar 10 capturas y parar
"""
import argparse
import os
import time
from datetime import datetime
from PIL import ImageGrab


def tomar_captura(output_dir: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"captura_{timestamp}.png"
    filepath = os.path.join(output_dir, filename)

    img = ImageGrab.grab()
    img.save(filepath)
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Monitor de capturas de pantalla")
    parser.add_argument("--interval", type=int, default=60,
                        help="Segundos entre capturas (default: 60)")
    parser.add_argument("--count", type=int, default=0,
                        help="Numero de capturas a tomar (0 = indefinido)")
    parser.add_argument("--output", type=str, default="capturas",
                        help="Carpeta de salida (default: ./capturas)")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    print(f"Monitor iniciado — intervalo: {args.interval}s | salida: {args.output}/")

    taken = 0
    try:
        while True:
            path = tomar_captura(args.output)
            taken += 1
            print(f"[{taken}] {path}")

            if args.count and taken >= args.count:
                print(f"Completado: {taken} capturas tomadas.")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\nDetenido. Total capturas: {taken}")


if __name__ == "__main__":
    main()
