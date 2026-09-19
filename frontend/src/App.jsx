import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState('loading...')

  useEffect(() => {
    fetch('/health')
      .then((response) => response.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('unreachable'))
  }, [])

  return (
    <main>
      <h1>food</h1>
      <p>API health: {health}</p>
    </main>
  )
}

export default App
