import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import IngredientDetail from './pages/detail/Ingredient'
import IngredientForm from './pages/edit/IngredientForm'
import Vocabularies from './pages/edit/Vocabularies'
import IngredientLibrary from './pages/library/IngredientLibrary'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // One user on a phone and a laptop: refetching on every window focus is
      // noise, and the data changes when this person changes it.
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/library/ingredient" replace />} />

            {/* Public reads. */}
            <Route path="/library/ingredient" element={<IngredientLibrary />} />
            <Route path="/ingredient/:id" element={<IngredientDetail />} />

            {/* Behind Cloudflare Access, by path. There is no route guard here
                and there must not be one: a guard in the browser would suggest
                the gate lives in this application, and the day someone
                believed that is the day it moves. */}
            <Route path="/edit/ingredient/new" element={<IngredientForm />} />
            <Route path="/edit/ingredient/:id" element={<IngredientForm />} />
            <Route path="/edit/vocabularies" element={<Vocabularies />} />

            <Route path="*" element={<Navigate to="/library/ingredient" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
