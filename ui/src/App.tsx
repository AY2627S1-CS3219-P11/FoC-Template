import { createBrowserRouter, RouterProvider, type RouteObject } from 'react-router-dom'
import ProtectedRoutes from './components/protectedRoutes/ProtectedRoutes'
import { routes } from './routes'

const appRoutes: RouteObject[] = [
  { path: routes.signIn, element: null },
  { path: routes.signOut, element: null },
  {
    element: <ProtectedRoutes />,
    children: [
      { path: routes.home, element: null },
      { path: routes.supplier, element: null },
    ],
  },
  { path: '*', element: <p>Page not found.</p> },
]

const router = createBrowserRouter(appRoutes)

const App = () => <RouterProvider router={router} />

export default App
