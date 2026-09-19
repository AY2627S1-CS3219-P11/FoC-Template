import { createBrowserRouter, RouterProvider, type RouteObject } from 'react-router-dom'
import ProtectedLayout from './components/protectedLayout/ProtectedLayout'
import ProtectedRoutes from './components/protectedRoutes/ProtectedRoutes'
import SignIn from './pages/authentication/signIn/SignIn'
import SignUp from './pages/authentication/signUp/SignUp'
import Home from './pages/home/Home'
import Profile from './pages/profile/Profile'
import Suppliers from './pages/suppliers/Suppliers'
import { routes } from './routes'

const appRoutes: RouteObject[] = [
  { path: routes.signIn, element: <SignIn /> },
  { path: routes.signUp, element: <SignUp /> },
  {
    element: <ProtectedRoutes />,
    children: [
      {
        element: <ProtectedLayout />,
        children: [
          { path: routes.home, element: <Home /> },
          { path: routes.profile, element: <Profile /> },
          { path: routes.suppliers, element: <Suppliers /> },
        ],
      },
    ],
  },
  { path: '*', element: <p>Page not found.</p> },
]

const router = createBrowserRouter(appRoutes)

const App = () => <RouterProvider router={router} />

export default App
