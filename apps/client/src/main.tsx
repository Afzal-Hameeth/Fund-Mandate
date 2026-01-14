import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './index.css'
import DashLayout from './layouts/DashLayout';
import Agent from './pages/agent';
import FundMandate from './pages/fundMandate';
import ScreeningAgent from './pages/screeningAgent';
import Error from './pages/Error';


const router = createBrowserRouter([
  {
    path: '/',
    element: <DashLayout />,
    errorElement: <Error />,
    children: [
      {
        index: true,
        element: <Agent />,
        errorElement: <Error />,
      },
      {
        path: 'fund-mandate',
        element: <FundMandate />,
        errorElement: <Error />,
      },
      {
        path: 'screening-agent',
        element: <ScreeningAgent />,
        errorElement: <Error />,
      },
    ],
  },
  {
    path: '/dashboard',
    element: <DashLayout />,
    errorElement: <Error />,
    children: [
      {
        index: true,
        element: <Agent />,
        errorElement: <Error />,
      },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
