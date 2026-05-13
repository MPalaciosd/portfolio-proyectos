import React, { useState, useEffect } from 'react';
// Importaciones necesarias de Firebase SDK
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, onAuthStateChanged } from 'firebase/auth';
import { 
  getFirestore, 
  collection, 
  addDoc, 
  onSnapshot, 
  query, 
  serverTimestamp,
  orderBy
} from 'firebase/firestore';

// ==========================================================
// --- CONFIGURACIÓN DE FIREBASE INTEGRADA (gestion-sw-ventas) ---
// ==========================================================
// Estos son los valores específicos de tu proyecto.
const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID
};

// Definición de variables para la aplicación local
const appId = firebaseConfig.projectId; 

let app;
let db;
let auth;

// Inicialización de Firebase
try {
  app = initializeApp(firebaseConfig);
  db = getFirestore(app);
  auth = getAuth(app);
} catch (error) {
  console.error("Error al inicializar Firebase. Revisa tu firebaseConfig:", error);
}

// Función auxiliar para obtener la ruta de la colección privada del usuario
// La ruta es: /artifacts/{projectId}/users/{userId}/sales_records
const getUserCollectionPath = (userId) => {
  return `/artifacts/${appId}/users/${userId}/sales_records`;
};

// ==========================================================
// --- COMPONENTE PRINCIPAL DE LA APLICACIÓN (App) ---
// ==========================================================
const App = () => {
  // Estado de Autenticación
  const [isAuthReady, setIsAuthReady] = useState(false);
  const [userId, setUserId] = useState(null);
  const [salesRecords, setSalesRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  // Estado del Formulario
  const [form, setForm] = useState({
    matricula: '',
    kilometraje: '',
    potenciaEstimada: '',
    antiguedad: '',
    tipoTransmision: '',
    neumaticos: '',
    historialMantenimiento: '',
    precioVendido: '',
  });

  // 1. Manejo de la Autenticación (Inicio de sesión anónimo para uso local)
  useEffect(() => {
    if (!auth) return;

    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (!user) {
        // Si no hay usuario, intenta iniciar sesión anónimamente
        try {
          const result = await signInAnonymously(auth);
          setUserId(result.user.uid);
          console.log(`Autenticación anónima exitosa. UID: ${result.user.uid}`);
        } catch (error) {
          console.error("Error al autenticar anónimamente:", error);
        }
      } else {
        setUserId(user.uid);
      }
      setIsAuthReady(true);
    });

    return () => unsubscribe(); // Limpiar el listener
  }, []);

  // 2. Carga de Datos (onSnapshot - Tiempo real)
  useEffect(() => {
    // Esperar a que el UserID esté listo
    if (!db || !isAuthReady || !userId) return;

    const salesCollectionRef = collection(db, getUserCollectionPath(userId));
    // Consulta: Ordenar por fecha de registro (descendente)
    const q = query(salesCollectionRef, orderBy('fechaRegistro', 'desc'));

    setLoading(true);

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const records = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      setSalesRecords(records);
      setLoading(false);
    }, (error) => {
      console.error("Error al cargar los registros de venta:", error);
      setLoading(false);
    });

    return () => unsubscribe(); // Limpiar el listener
  }, [isAuthReady, userId]);

  // Manejador de cambios en el formulario
  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  // Manejador de envío del formulario (Guardar en Firestore)
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!db || !userId) {
      setMessage('Error: El sistema de base de datos no está listo. Intenta recargar.');
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      // Validaciones básicas
      if (!form.matricula || !form.precioVendido) {
        setMessage('Por favor, ingresa la Matrícula y el Precio de Venta.');
        setLoading(false);
        return;
      }
      
      const salesCollectionRef = collection(db, getUserCollectionPath(userId));
      
      // Construir el objeto de datos a guardar
      const dataToSave = {
        ...form,
        // Convertir campos numéricos a tipo Number
        kilometraje: Number(form.kilometraje) || null,
        antiguedad: Number(form.antiguedad) || null,
        potenciaEstimada: Number(form.potenciaEstimada) || null,
        precioVendido: Number(form.precioVendido),
        fechaRegistro: serverTimestamp(), // Marca de tiempo del servidor para ordenar
        registradoPor: userId,
      };

      await addDoc(salesCollectionRef, dataToSave);

      // Limpiar formulario y mostrar éxito
      setForm({
        matricula: '',
        kilometraje: '',
        potenciaEstimada: '',
        antiguedad: '',
        tipoTransmision: '',
        neumaticos: '',
        historialMantenimiento: '',
        precioVendido: '',
      });
      setMessage('✅ ¡Venta registrada exitosamente!');
    } catch (error) {
      console.error("Error al guardar el registro de venta:", error);
      setMessage(`❌ Error al guardar: ${error.message}. Asegúrate de que tus Reglas de Firestore permiten escribir.`);
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(''), 5000); 
    }
  };

  // Componente de Campo de Formulario reutilizable
  const InputField = ({ label, name, type = 'text', placeholder, required = false }) => (
    <div className="flex flex-col space-y-1">
      <label htmlFor={name} className="text-sm font-medium text-gray-300">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {type === 'textarea' ? (
        <textarea
          id={name}
          name={name}
          value={form[name]}
          onChange={handleChange}
          rows="3"
          placeholder={placeholder}
          required={required}
          className="p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-sky-500 focus:border-sky-500 transition duration-150"
        />
      ) : (
        <input
          id={name}
          name={name}
          type={type}
          value={form[name]}
          onChange={handleChange}
          placeholder={placeholder}
          required={required}
          className="p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:ring-sky-500 focus:border-sky-500 transition duration-150"
        />
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-900 text-white font-inter p-4 sm:p-8">
      <div className="max-w-6xl mx-auto">
        
        {/* Encabezado y Estado de Auth */}
        <header className="mb-8 border-b border-gray-700 pb-4">
          <h1 className="text-4xl font-extrabold text-sky-400 mb-2">
            Registro de Ventas de Vehículos
          </h1>
          <p className="text-gray-400">
            Introduce los detalles de la venta del coche. Los datos se guardan en tu cuenta privada.
          </p>
          <p className="text-sm text-gray-500 mt-2">
            ID de Usuario Actual (para referencia): <span className="font-mono text-xs bg-gray-800 p-1 rounded">{userId || 'Cargando...'}</span>
          </p>
        </header>

        {/* Formulario de Registro */}
        <section className="bg-gray-800 p-6 sm:p-8 rounded-xl shadow-2xl mb-10">
          <h2 className="text-2xl font-semibold mb-6 border-b border-gray-700 pb-3 text-sky-300">
            Detalles de la Venta
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Información Básica Obligatoria */}
              <InputField 
                label="Matrícula" 
                name="matricula" 
                placeholder="Ej: ABC-1234" 
                required 
              />
              <InputField 
                label="Precio Vendido (€)" 
                name="precioVendido" 
                type="number" 
                placeholder="Ej: 15000" 
                required 
              />
              <InputField 
                label="Antigüedad (Años)" 
                name="antiguedad" 
                type="number" 
                placeholder="Ej: 5" 
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Características del Coche */}
              <InputField 
                label="Kilometraje (Km)" 
                name="kilometraje" 
                type="number" 
                placeholder="Ej: 85000" 
              />
              <InputField 
                label="Potencia Estimada (CV)" 
                name="potenciaEstimada" 
                type="number" 
                placeholder="Ej: 150" 
              />
              <InputField 
                label="Tipo de Transmisión" 
                name="tipoTransmision" 
                placeholder="Ej: Automática / Manual" 
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Neumáticos e Historial */}
              <InputField 
                label="Estado/Tipo de Neumáticos" 
                name="neumaticos" 
                type="textarea"
                placeholder="Ej: Michelin Pilot Sport 4, 70% de vida útil" 
              />
              <InputField 
                label="Historial de Mantenimiento" 
                name="historialMantenimiento" 
                type="textarea"
                placeholder="Ej: Última revisión hace 3 meses. Cambio de correa a los 100k km." 
              />
            </div>

            {/* Mensajes y Botón */}
            {message && (
              <div className={`p-3 rounded-lg text-center font-semibold ${message.startsWith('✅') ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
                {message}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !isAuthReady}
              className="w-full py-3 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-lg shadow-lg transition duration-200 ease-in-out disabled:bg-sky-800 disabled:cursor-not-allowed flex items-center justify-center"
            >
              {loading ? (
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : 'Guardar Venta'}
            </button>
          </form>
        </section>

        {/* Historial de Registros */}
        <section>
          <h2 className="text-2xl font-semibold mb-6 border-b border-gray-700 pb-3 text-sky-300">
            Tu Historial de Registros
          </h2>
          
          {loading && !salesRecords.length && <p className="text-center text-gray-400">Cargando historial...</p>}

          {!loading && !salesRecords.length && (
            <div className="text-center text-gray-400 p-10 bg-gray-800 rounded-xl">
              Aún no has registrado ninguna venta. ¡Empieza a introducir datos!
            </div>
          )}

          {salesRecords.length > 0 && (
            <div className="overflow-x-auto bg-gray-800 rounded-xl shadow-xl">
              <table className="min-w-full divide-y divide-gray-700">
                <thead className="bg-gray-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Matrícula</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Precio</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Km</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Antigüedad (Años)</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Transmisión</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Fecha</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {salesRecords.map((record) => (
                    <tr key={record.id} className="hover:bg-gray-700 transition duration-150">
                      <td className="px-6 py-4 whitespace-nowrap font-semibold text-sky-400">{record.matricula}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(record.precioVendido)}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{record.kilometraje?.toLocaleString('es-ES') || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{record.antiguedad || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">{record.tipoTransmision || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                        {record.fechaRegistro ? new Date(record.fechaRegistro.seconds * 1000).toLocaleDateString('es-ES') : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </section>

      </div>
    </div>
  );
};

export default App;
