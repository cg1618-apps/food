// Frontend: the route table.
//
// Every page the app will have is registered here now, each with its own
// component, so a later change touches only its page's file. Reads are public;
// everything that creates, updates or deletes is under /edit, which Cloudflare
// Access gates by path in front of the box.
//
// There is no route guard here and there must not be one: a guard in the
// browser would suggest the gate lives in this application, and the day
// someone believed that is the day it moves. EditSignIn wraps the /edit pages
// and is not one: it renders every page whatever happens, and only sends a
// signed-out browser through the Access login as the page opens.
import { Navigate, Route, Routes } from 'react-router-dom'

import EditSignIn from './components/layout/EditSignIn'
import Layout from './components/layout/Layout'
import Redirect from './components/layout/Redirect'
import DishDetail from './pages/detail/Dish'
import IngredientDetail from './pages/detail/Ingredient'
import NoteDetail from './pages/detail/Note'
import RecipeDetail from './pages/detail/Recipe'
import DishForm from './pages/edit/DishForm'
import ImageLibrary from './pages/edit/ImageLibrary'
import IngredientForm from './pages/edit/IngredientForm'
import NoteForm from './pages/edit/NoteForm'
import RecipeForm from './pages/edit/RecipeForm'
import ScheduleForm from './pages/edit/ScheduleForm'
import Settings from './pages/edit/Settings'
import TbdForm from './pages/edit/TbdForm'
import TemplateForm from './pages/edit/TemplateForm'
import DishLibrary from './pages/library/DishLibrary'
import IngredientLibrary from './pages/library/IngredientLibrary'
import NoteLibrary from './pages/library/NoteLibrary'
import RecipeLibrary from './pages/library/RecipeLibrary'
import Schedule from './pages/library/Schedule'
import Tbd from './pages/library/Tbd'
import NotFound from './pages/NotFound'

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/recipes" replace />} />

        {/* Public reads. */}
        <Route path="/dishes" element={<DishLibrary />} />
        <Route path="/dishes/:id" element={<DishDetail />} />
        <Route path="/recipes" element={<RecipeLibrary />} />
        <Route path="/recipes/:id" element={<RecipeDetail />} />
        <Route path="/ingredients" element={<IngredientLibrary />} />
        <Route path="/ingredients/:id" element={<IngredientDetail />} />
        <Route path="/notes" element={<NoteLibrary />} />
        <Route path="/notes/:id" element={<NoteDetail />} />
        <Route path="/schedule" element={<Schedule />} />
        <Route path="/tbd" element={<Tbd />} />

        {/* Behind Cloudflare Access, by path. */}
        <Route element={<EditSignIn />}>
          <Route path="/edit/dishes/new" element={<DishForm />} />
          <Route path="/edit/dishes/:id" element={<DishForm />} />
          <Route path="/edit/recipes/new" element={<RecipeForm />} />
          <Route path="/edit/recipes/:id" element={<RecipeForm />} />
          <Route path="/edit/templates/new" element={<TemplateForm />} />
          <Route path="/edit/templates/:id" element={<TemplateForm />} />
          <Route path="/edit/ingredients/new" element={<IngredientForm />} />
          <Route path="/edit/ingredients/:id" element={<IngredientForm />} />
          <Route path="/edit/notes/new" element={<NoteForm />} />
          <Route path="/edit/notes/:id" element={<NoteForm />} />
          <Route path="/edit/settings" element={<Settings />} />
          <Route path="/edit/images" element={<ImageLibrary />} />
          <Route path="/edit/schedule" element={<ScheduleForm />} />
          <Route path="/edit/tbd" element={<TbdForm />} />
        </Route>

        {/* 設定 is a write page, so it lives under /edit; the short path is
            what someone types. */}
        <Route path="/settings" element={<Navigate to="/edit/settings" replace />} />

        {/* The first release's paths, so bookmarks survive. The query string
            rides along - /library/ingredient?category=3 still filters. */}
        <Route path="/library/ingredient" element={<Redirect to={() => '/ingredients'} />} />
        <Route path="/ingredient/:id" element={<Redirect to={({ id }) => `/ingredients/${id}`} />} />
        <Route
          path="/edit/ingredient/new"
          element={<Redirect to={() => '/edit/ingredients/new'} />}
        />
        <Route
          path="/edit/ingredient/:id"
          element={<Redirect to={({ id }) => `/edit/ingredients/${id}`} />}
        />
        <Route path="/edit/vocabularies" element={<Redirect to={() => '/edit/settings'} />} />
        {/* The dish form's path as the design named it; the form lives at
            /edit/dishes/:id like every other edit page. */}
        <Route path="/edit/dishes/:id/edit" element={<Redirect to={({ id }) => `/edit/dishes/${id}`} />} />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
