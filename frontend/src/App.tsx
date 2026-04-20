import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import PresentationWorkflow from './components/PresentationWorkflow'
import Login from './components/Login'
import Register from './components/Register'

// Simple auth check
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('access_token')
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <PresentationWorkflow />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
