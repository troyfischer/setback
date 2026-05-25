import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ThemeToggle } from "./components/ThemeToggle";
import { AuthProvider, useAuth } from "./context/auth";
import { useTheme } from "./hooks/useTheme";
import { GameScreen } from "./screens/GameScreen";
import { LobbyScreen } from "./screens/LobbyScreen";
import { WelcomeScreen } from "./screens/WelcomeScreen";

function LoadingSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-gold border-t-transparent" />
        <p className="text-sm font-semibold text-slate-400 dark:text-blue-200/70">
          Shuffling the deck…
        </p>
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { hydrated, accessToken, currentUser } = useAuth();
  if (!hydrated) return <LoadingSpinner />;
  if (!accessToken || !currentUser) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RootRoute() {
  const { hydrated, accessToken, currentUser } = useAuth();
  if (!hydrated) return <LoadingSpinner />;
  if (accessToken && currentUser) return <Navigate to="/lobby" replace />;
  return <WelcomeScreen />;
}

function AppContent() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="relative min-h-dvh">
      <div className="fixed right-4 bottom-4 z-50 md:top-4 md:bottom-auto">
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
      </div>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route
          path="/lobby"
          element={
            <ProtectedRoute>
              <LobbyScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/lobby/:gameId"
          element={
            <ProtectedRoute>
              <LobbyScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/game/:gameId"
          element={
            <ProtectedRoute>
              <GameScreen />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </AuthProvider>
  );
}
