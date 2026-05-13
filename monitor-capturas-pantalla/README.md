# Monitor de Capturas de Pantalla

Script de monitorización que toma capturas de pantalla a intervalos configurables y las guarda con timestamp.

## Stack

- **Python** + **Pillow** (PIL)

## Uso

```bash
pip install -r requirements.txt
```

```bash
# Captura cada 60 segundos (indefinido)
python monitor.py

# Captura cada 30 segundos
python monitor.py --interval 30

# Tomar exactamente 10 capturas
python monitor.py --count 10

# Carpeta de salida personalizada
python monitor.py --output mis_capturas
```

Las capturas se guardan en `./capturas/captura_YYYYMMDD_HHMMSS.png`.
