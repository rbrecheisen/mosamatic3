import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './layout';
import { ProtectedRoute } from './protectedroute';
import { ErrorPage } from './pages/errorpage'
import { LoginPage } from './pages/auth/loginpage';
import { RegistrationPage } from './pages/auth/registrationpage';
import { HomePage } from './pages/homepage';
import { DataPage } from './pages/data/datapage';
// import { AnalysesHomePage } from '../features/analyses/AnalysesHomePage';
// import { AnalysisTypePage } from '../features/analyses/AnalysisTypePage';
// import { AnalysisRunCreatePage } from '../features/analyses/AnalysisRunCreatePage';
// import { AnalysisRunDetailPage } from '../features/analyses/AnalysisRunDetailPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <Navigate to="/home" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegistrationPage /> },
      {
        element: <ProtectedRoute />,
        children: [
          { path: 'home', element: <HomePage /> },
          { path: 'data', element: <DataPage /> },
          // { path: 'analyses', element: <AnalysesHomePage /> },
          // { path: 'analyses/:analysisType', element: <AnalysisTypePage /> },
          // { path: 'analyses/:analysisType/new', element: <AnalysisRunCreatePage /> },
          // { path: 'runs/:runId', element: <AnalysisRunDetailPage /> },
        ],
      },
    ],
  },
]);