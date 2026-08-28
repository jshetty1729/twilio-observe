import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Theme } from '@twilio-paste/core/theme';
import { DashboardPage } from './pages/DashboardPage';
import { CallDetailPage } from './pages/CallDetailPage';

export const App: React.FC = () => (
  <Theme.Provider theme="default">
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/call/:callSid" element={<CallDetailPage />} />
      </Routes>
    </BrowserRouter>
  </Theme.Provider>
);
