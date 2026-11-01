import { Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
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
          <Route path="/wardrobe" element={<Wardrobe />} />
          <Route path="/add-item" element={<AddItem />} />
          <Route path="/stylist" element={<AIStylist />} />
          <Route path="/recommendations" element={<Recommendations />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
