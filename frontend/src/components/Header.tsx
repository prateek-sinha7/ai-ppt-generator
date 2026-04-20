import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../services/api'

export default function Header() {
  const [userEmail, setUserEmail] = useState<string>('')
  const navigate = useNavigate()

  useEffect(() => {
    // Fetch current user info
    apiClient.get('/auth/me')
      .then(response => {
        setUserEmail(response.data.email)
      })
      .catch(err => {
        console.error('Failed to fetch user info:', err)
      })
  }, [])

  const handleLogout = () => {
    const refreshToken = localStorage.getItem('refresh_token')
    
    // Call logout endpoint if we have a refresh token
    if (refreshToken) {
      apiClient.post('/auth/logout', { refresh_token: refreshToken })
        .catch(err => console.error('Logout error:', err))
    }
    
    // Clear tokens and redirect
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/login')
  }

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              AI Presentation Intelligence Platform
            </h1>
          </div>
          <div className="flex items-center gap-4">
            {userEmail && (
              <span className="text-sm text-gray-600">
                {userEmail}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
