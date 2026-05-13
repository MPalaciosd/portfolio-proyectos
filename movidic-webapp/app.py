import os
import pyodbc
from flask import Flask, request, render_template

# Inicialización de la aplicación Flask
app = Flask(__name__, template_folder='.') # Le decimos a Flask que busque plantillas aquí

# Función para obtener la cadena de conexión de las variables de entorno de Azure
def get_db_connection():
    # Azure App Service guarda la cadena de conexión 'SQLConnection' en esta variable de entorno
    conn_string = os.environ.get('SQLConnection')
    if not conn_string:
        raise ValueError("ERROR: La cadena de conexión 'SQLConnection' no está configurada en Azure.")
    
    # IMPORTANTE: pyodbc requiere que el driver esté instalado en el entorno.
    # Azure App Service (Linux Python) tiene el driver ODBC disponible.
    return pyodbc.connect(conn_string)

# Ruta principal: Muestra el formulario (index.html)
@app.route('/')
def index():
    return render_template('index.html') 

# Ruta para manejar el envío del formulario (Método POST)
@app.route('/guardar-datos', methods=['POST'])
def guardar_datos():
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Recoger datos del formulario
        form_data = request.form

        # 2. Sentencia INSERT con parámetros seguros
        sql_insert = """
        INSERT INTO TasacionVivienda (
            AreaTotalM2, NumDormitorios, NumBanyos, AntiguedadAnios, ZonaClave, 
            TieneAscensor, EstadoConservacion, PrecioFinal, MetodoPago, GuardadoPor
        ) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # 3. Preparar los datos en el orden de las columnas de la tabla:
        datos = (
            float(form_data['AreaTotalM2']),
            int(form_data['NumDormitorios']),
            int(form_data['NumBanyos']),
            int(form_data.get('AntiguedadAnios', 0) or 0),
            form_data.get('ZonaClave'),
            int(form_data['TieneAscensor']),
            form_data.get('EstadoConservacion'),
            float(form_data['PrecioFinal']),
            form_data.get('MetodoPago'),
            form_data['GuardadoPor']
        )

        # 4. Ejecutar la inserción
        cursor.execute(sql_insert, datos)
        conn.commit()
        
        return "<h1> Datos guardados con éxito en Azure SQL!</h1><p><a href='/'>Volver al formulario</a></p>"

    except Exception as e:
        return f"<h1> ERROR de Base de Datos/Conexión:</h1><p>{e}</p><p>Asegúrate de haber configurado la Cadena de Conexión en App Service.</p>"
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Se utiliza un puerto diferente si se prueba localmente para evitar conflictos
    app.run(host='0.0.0.0', port=8000, debug=True)