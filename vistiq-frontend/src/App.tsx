import { Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import Wardrobe from './pages/Wardrobe'
import AddItem from './pages/AddItem'
import AIStylist from './pages/AIStylist'
import Recommendations from './pages/Recommendations'

function App() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/wardrobe"
            element={
              <ProtectedRoute>
                <Wardrobe />
              </ProtectedRoute>
            }
          />
          <Route
            path="/add-item"
            element={
              <ProtectedRoute>
                <AddItem />
              </ProtectedRoute>
            }
          />
          <Route
            path="/stylist"
            element={
              <ProtectedRoute>
                <AIStylist />
              </ProtectedRoute>
            }
          />
          <Route
            path="/recommendations"
            element={
              <ProtectedRoute>
                <Recommendations />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  )
}

export default App
