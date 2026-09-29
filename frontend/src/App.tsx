import { BrowserRouter } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { AppRoutes } from './routes/AppRoutes'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
