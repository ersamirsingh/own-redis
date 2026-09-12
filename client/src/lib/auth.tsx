"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { apiClient, clearTokens, getAccessToken, setTokens } from "./api";
import { AuthResponse, User } from "./types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refreshProfile = async () => {
    try {
      const activeToken = getAccessToken();
      if (!activeToken) {
        setUser(null);
        setToken(null);
        return;
      }
      const userData = await apiClient<User>("/api/auth/me");
      setUser(userData);
      setToken(activeToken);
      localStorage.setItem("pyredis_user", JSON.stringify(userData));
    } catch {
      setUser(null);
      setToken(null);
      clearTokens();
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      const savedUser = localStorage.getItem("pyredis_user");
      const activeToken = getAccessToken();

      if (savedUser && activeToken) {
        try {
          setUser(JSON.parse(savedUser));
          setToken(activeToken);
        } catch {
          // JSON parse failure
        }
      }

      if (activeToken) {
        await refreshProfile();
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiClient<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    setToken(data.access_token);
    localStorage.setItem("pyredis_user", JSON.stringify(data.user));
    router.push("/dashboard");
  };

  const signup = async (email: string, name: string, password: string) => {
    const data = await apiClient<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    });

    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    setToken(data.access_token);
    localStorage.setItem("pyredis_user", JSON.stringify(data.user));
    router.push("/dashboard");
  };

  const logout = () => {
    clearTokens();
    setUser(null);
    setToken(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        signup,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
