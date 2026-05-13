import pdfplumber
import os
import pandas as pd

folder_path = './pdf_incidencias' 
output_file = 'reporte_final.csv'
data_list = []

print("--- INICIANDO EXTRACCIÓN ---")

if not os.path.exists(folder_path):
    print(f"Error: No encuentro la carpeta {folder_path}")
else:
    # Obtenemos la lista de archivos para saber el total
    archivos = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    total = len(archivos)
    print(f"Se han encontrado {total} archivos. Empezando...")

    for i, filename in enumerate(archivos, 1):
        try:
            with pdfplumber.open(os.path.join(folder_path, filename)) as pdf:
                texto = pdf.pages[0].extract_text()
                data_list.append({
                    "Archivo": filename,
                    "Contenido": texto.replace('\n', ' ') if texto else ""
                })
            
            # ESTO ES LO NUEVO: Te avisará cada 50 archivos
            if i % 50 == 0 or i == total:
                print(f"Progreso: {i}/{total} archivos procesados ({(i/total)*100:.1f}%)")

        except Exception as e:
            print(f"Error en {filename}: {e}")

    # Guardar el resultado
    df = pd.DataFrame(data_list)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n¡FINALIZADO! El archivo '{output_file}' está listo.")