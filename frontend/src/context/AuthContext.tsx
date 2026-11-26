"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { User, AuthResponse } from "@/types/auth";
import {
  apiRequest,
  hasRefreshSessionHint,
  setAccessToken,
  singleFlightRefreshToken,
} from "@/lib/api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (loginStr: string, password: string) => Promise<AuthResponse>;
  register: (data: {
    email: string;
    phone: string;
    full_name: string;
    password: string;
    role?: string;
    city_id?: number;
    locality_id?: number;
  }) => Promise<AuthResponse>;
  requestOtp: (phone: string, purpose?: string) => Promise<{
    message: string;
    phone?: string;
    sandbox_code?: string;
    dev_notice?: string;
    is_sandbox?: boolean;
  }>;
  verifyOtp: (phone: string, otp: string, purpose?: string) => Promise<AuthResponse>;
  forgotPassword: (emailOrPhone: string) => Promise<{
    message: string;
    phone?: string;
    sandbox_code?: string;
    dev_notice?: string;
    is_sandbox?: boolean;
  }>;
  resetPassword: (emailOrPhone: string, otp: string, newPassword: string) => Promise<{ success: boolean; message: string }>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  deactivateAccount: () => Promise<void>;
  updateProfile: (data: {
    full_name?: string;
    avatar_url?: string;
    city_id?: number;
    locality_id?: number | null;
    preferred_language?: string;
    bio?: string;
    emergency_phone?: string;
  }) => Promise<User>;
  refreshUser: () => Promise<void>;
  isAuthModalOpen: boolean;
  openAuthModal: (tab?: "login" | "register" | "otp") => void;
  closeAuthModal: () => void;
  authModalInitialTab: "login" | "register" | "otp";
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalInitialTab, setAuthModalInitialTab] = useState<"login" | "register" | "otp">("login");

  const openAuthModal = (tab: "login" | "register" | "otp" = "login") => {
    setAuthModalInitialTab(tab);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  const refreshUser = useCallback(async () => {
    try {
      // Avoid unnecessary guest POST /auth/refresh (401) when no refresh session exists
      if (!hasRefreshSessionHint()) {
        setUser(null);
        setToken(null);
        setAccessToken(null);
        return;
      }

      // Restore or refresh session using HttpOnly cookie rotation
      const activeToken = await singleFlightRefreshToken();
      if (!activeToken) {
        setUser(null);
        setToken(null);
        setAccessToken(null);
        return;
      }

      setToken(activeToken);
      setAccessToken(activeToken);

      const userData = await apiRequest<User>("/auth/me");
      setUser(userData);
    } catch {
      setUser(null);
      setToken(null);
      setAccessToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();

    const handleSessionExpired = () => {
      setUser(null);
      setToken(null);
      setAccessToken(null);
    };

    window.addEventListener("gobeyond_session_expired", handleSessionExpired);
    return () => {
      window.removeEventListener("gobeyond_session_expired", handleSessionExpired);
    };
  }, [refreshUser]);

  const login = async (loginStr: string, password: string): Promise<AuthResponse> => {
    const data = await apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: loginStr, password }),
    });

    setAccessToken(data.access_token);
    setToken(data.access_token);
    const userData = await apiRequest<User>("/auth/me");
    setUser(userData);
    closeAuthModal();
    return data;
  };

  const register = async (regData: {
    email: string;
    phone: string;
    full_name: string;
    password: string;
    role?: string;
    city_id?: number;
    locality_id?: number;
  }): Promise<AuthResponse> => {
    const data = await apiRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(regData),
    });

    setAccessToken(data.access_token);
    setToken(data.access_token);
    const userData = await apiRequest<User>("/auth/me");
    setUser(userData);
    closeAuthModal();
    return data;
  };

  const requestOtp = async (phone: string, purpose = "login") => {
    return await apiRequest<{
      message: string;
      phone?: string;
      sandbox_code?: string;
      dev_notice?: string;
      is_sandbox?: boolean;
    }>("/auth/request-otp", {
      method: "POST",
      body: JSON.stringify({ phone, purpose }),
    });
  };

  const verifyOtp = async (phone: string, otp: string, purpose = "login"): Promise<AuthResponse> => {
    const data = await apiRequest<AuthResponse>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ phone, otp, purpose }),
    });

    setAccessToken(data.access_token);
    setToken(data.access_token);
    const userData = await apiRequest<User>("/auth/me");
    setUser(userData);
    closeAuthModal();
    return data;
  };

  const forgotPassword = async (emailOrPhone: string) => {
    return await apiRequest<{
      message: string;
      phone?: string;
      sandbox_code?: string;
      dev_notice?: string;
      is_sandbox?: boolean;
    }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email_or_phone: emailOrPhone }),
    });
  };

  const resetPassword = async (emailOrPhone: string, otp: string, newPassword: string) => {
    return await apiRequest<{ success: boolean; message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        email_or_phone: emailOrPhone,
        otp,
        new_password: newPassword,
      }),
    });
  };

  const logout = async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } catch {
      // Clear local memory regardless of network response
    }
    setAccessToken(null);
    setToken(null);
    setUser(null);
  };

  const logoutAll = async () => {
    try {
      await apiRequest("/auth/logout-all", { method: "POST" });
    } catch {
      // Clear local memory regardless of network response
    }
    setAccessToken(null);
    setToken(null);
    setUser(null);
  };

  const deactivateAccount = async () => {
    await apiRequest("/auth/deactivate", { method: "POST" });
    setAccessToken(null);
    setToken(null);
    setUser(null);
  };

  const updateProfile = async (data: {
    full_name?: string;
    avatar_url?: string;
    city_id?: number;
    locality_id?: number | null;
    preferred_language?: string;
    bio?: string;
    emergency_phone?: string;
  }): Promise<User> => {
    const updated = await apiRequest<User>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(data),
    });
    setUser(updated);
    return updated;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        requestOtp,
        verifyOtp,
        forgotPassword,
        resetPassword,
        logout,
        logoutAll,
        deactivateAccount,
        updateProfile,
        refreshUser,
        isAuthModalOpen,
        openAuthModal,
        closeAuthModal,
        authModalInitialTab,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
