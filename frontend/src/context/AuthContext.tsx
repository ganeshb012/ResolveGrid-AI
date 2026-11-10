import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { User, UserRole } from '../types';
import { api } from '../api/client';
import { wsClient } from '../api/ws';
import { Language, translations, Translations } from '../i18n/translations';

interface AuthContextType {
  user: User | null;
  token: string | null;
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
  login: (token: string, user: User) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Safely registers the router's navigate hook when inside a Router context
const RouterNavigationListener: React.FC<{
  onRegister: (nav: (path: string) => void) => void;
}> = ({ onRegister }) => {
  const navigate = useNavigate();
  useEffect(() => {
    onRegister(navigate);
    return () => {
      onRegister(() => {});
    };
  }, [navigate, onRegister]);
  return null;
};

const SafeRouterBridge: React.FC<{
  onRegister: (nav: (path: string) => void) => void;
}> = ({ onRegister }) => {
  const inRouter = useInRouterContext();
  if (!inRouter) return null;
  return <RouterNavigationListener onRegister={onRegister} />;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => {
    try {
      return typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    } catch {
      return null;
    }
  });
  const [user, setUser] = useState<User | null>(() => {
    try {
      if (typeof window !== 'undefined') {
        const savedUser = localStorage.getItem('user');
        return savedUser ? JSON.parse(savedUser) : null;
      }
      return null;
    } catch {
      return null;
    }
  });
  const [language, setLanguageState] = useState<Language>(() => {
    try {
      return (typeof window !== 'undefined' && (localStorage.getItem('lang') as Language)) || 'en';
    } catch {
      return 'en';
    }
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const navigateRef = useRef<((path: string) => void) | null>(null);

  const registerNavigate = useCallback((nav: (path: string) => void) => {
    navigateRef.current = nav;
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('lang', lang);
  };

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
    wsClient.connect(newUser.id);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    wsClient.disconnect();
    if (navigateRef.current) {
      navigateRef.current('/login');
    } else if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');

      if (savedToken && savedUser) {
        try {
          const parsed = JSON.parse(savedUser);
          setUser(parsed);
          wsClient.connect(parsed.id);
        } catch {
          logout();
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const t = translations[language];

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        language,
        setLanguage,
        t,
        login,
        logout,
        isLoading,
      }}
    >
      <SafeRouterBridge onRegister={registerNavigate} />
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
