import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import App from './App.tsx'
import './index.css'

// "/" is a new conversation; "/c/:sessionId" is a saved one (shareable, reloadable, back/forward work).
const router = createBrowserRouter([
  { path: '/', element: <App /> },
  { path: '/c/:sessionId', element: <App /> },
  { path: '*', element: <Navigate to="/" replace /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
