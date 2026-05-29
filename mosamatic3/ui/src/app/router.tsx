import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './layout';
import { ProtectedRoute } from './protectedroute';
import { ErrorPage } from './pages/errorpage'
import { LoginPage } from './pages/auth/loginpage';
import { RegistrationPage } from './pages/auth/registrationpage';
import { HomePage } from './pages/homepage';
import { DataPage } from './pages/data/datapage';
import { DataDetailsPage } from './pages/data/datadetailspage';
import { AnalysisPage } from './pages/analysis/analysispage';
import { AdminRoute } from './adminroute';
import { AdminPage } from './pages/admin/adminpage';

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
          { path: 'data/:datasetId', element: <DataDetailsPage /> },
          { path: 'analysis', element: <AnalysisPage /> },
          {
            element: <AdminRoute />,
            children: [
              { path: 'admin', element: <AdminPage /> },
            ],
          },
          // { path: 'analysis', element: <AnalysisHomePage /> },
          // { path: 'analysis/:analysisType', element: <AnalysisTypePage /> },
          // { path: 'analysis/:analysisType/new', element: <AnalysisRunCreatePage /> },
          // { path: 'runs/:runId', element: <AnalysisRunDetailPage /> },
        ],
      },
    ],
  },
]);