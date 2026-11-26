"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  Lock,
  Mail,
  Smartphone,
  Eye,
  EyeOff,
  ArrowRight,
  Sparkles,
  AlertCircle,
  KeyRound,
  ShieldCheck
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login, requestOtp, verifyOtp } = useAuth();

  const [authMode, setAuthMode] = useState<"password" | "otp">("password");
  const [loginInput, setLoginInput] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // OTP mode state
  const [phone, setPhone] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [devNotice, setDevNotice] = useState<string | null>(null);
  const [sandboxCode, setSandboxCode] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await login(loginInput.trim(), password);
      if (res.role === "super_admin") {
        router.push("/admin");
      } else if (res.role.startsWith("partner_")) {
        router.push("/partner");
      } else {
        router.push("/profile");
      }
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please verify your email/phone and password.");
    } finally {
      setLoading(false);
    }
  };

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone || phone.length < 10) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await requestOtp(phone.trim(), "login");
      setOtpSent(true);
      if (res.sandbox_code) {
        setSandboxCode(res.sandbox_code);
        setDevNotice(res.dev_notice || "Development Sandbox Mode");
      }
    } catch (err: any) {
      setError(err.message || "Failed to dispatch verification code.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpCode || otpCode.length < 4) {
      setError("Please enter the verification code.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await verifyOtp(phone.trim(), otpCode.trim(), "login");
      if (res.role === "super_admin") {
        router.push("/admin");
      } else if (res.role.startsWith("partner_")) {
        router.push("/partner");
      } else {
        router.push("/profile");
      }
    } catch (err: any) {
      setError(err.message || "Invalid verification code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex items-center justify-center space-x-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-rose-500 flex items-center justify-center font-black text-xl shadow-lg shadow-brand-500/20">
            GB
          </div>
          <span className="text-2xl font-black tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-brand-400">
            GO BEYOND
          </span>
        </div>
        <h2 className="mt-4 text-center text-2xl font-extrabold text-white">
          Sign In to Your Account
        </h2>
        <p className="mt-1 text-center text-xs text-gray-400">
          Discover. Book. Experience Hyderabad&apos;s best entertainment.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-gray-900/90 backdrop-blur-xl py-8 px-6 shadow-2xl rounded-3xl border border-gray-800 space-y-6">
          
          {/* Auth Mode Toggle */}
          <div className="grid grid-cols-2 p-1 bg-gray-950 rounded-2xl border border-gray-800 text-xs font-semibold">
            <button
              type="button"
              onClick={() => { setAuthMode("password"); setError(null); }}
              className={`py-2 rounded-xl transition ${authMode === "password" ? "bg-brand-600 text-white shadow" : "text-gray-400 hover:text-white"}`}
            >
              Password Login
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode("otp"); setError(null); }}
              className={`py-2 rounded-xl transition ${authMode === "otp" ? "bg-brand-600 text-white shadow" : "text-gray-400 hover:text-white"}`}
            >
              Mobile OTP Login
            </button>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {authMode === "password" ? (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Email or Mobile Number
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    placeholder="you@domain.com or 9876543210"
                    value={loginInput}
                    onChange={(e) => setLoginInput(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Password
                  </label>
                  <Link
                    href="/forgot-password"
                    className="text-[11px] text-brand-400 hover:text-brand-300 transition"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-10 pr-10 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-gray-500 hover:text-gray-300 transition"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <span>{loading ? "Authenticating..." : "Sign In"}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              {!otpSent ? (
                <form onSubmit={handleSendOtp} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                      Mobile Number
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500 text-xs font-semibold">
                        +91
                      </div>
                      <input
                        type="tel"
                        required
                        maxLength={10}
                        placeholder="9876543210"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                        className="w-full pl-12 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || phone.length < 10}
                    className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
                  >
                    <span>{loading ? "Sending Code..." : "Get OTP Code"}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-4">
                  {sandboxCode && (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs space-y-1">
                      <div className="flex items-center space-x-1.5 text-amber-400 font-bold text-[11px]">
                        <KeyRound className="w-3.5 h-3.5" />
                        <span>DEVELOPMENT SANDBOX CODE</span>
                      </div>
                      <p className="text-gray-300 font-mono text-sm tracking-widest font-black">
                        {sandboxCode}
                      </p>
                      <p className="text-[10px] text-gray-500 leading-tight">
                        {devNotice}
                      </p>
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider">
                        Enter 6-Digit OTP
                      </label>
                      <button
                        type="button"
                        onClick={() => { setOtpSent(false); setOtpCode(""); }}
                        className="text-[11px] text-brand-400 hover:text-brand-300"
                      >
                        Change number
                      </button>
                    </div>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      placeholder="123456"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      className="w-full text-center tracking-widest text-lg py-2.5 bg-gray-950 border border-gray-800 rounded-xl font-mono text-white focus:outline-none focus:border-brand-500 transition"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading || otpCode.length < 4}
                    className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
                  >
                    <span>{loading ? "Verifying..." : "Verify & Sign In"}</span>
                    <ShieldCheck className="w-4 h-4" />
                  </button>
                </form>
              )}
            </div>
          )}

          {/* Quick Demo Credentials */}
          <div className="pt-4 border-t border-gray-800/80">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mb-2 text-center">
              Quick Test Credentials
            </p>
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <button
                type="button"
                onClick={() => {
                  setAuthMode("password");
                  setLoginInput("customer@gobeyond.com");
                  setPassword("Customer@123");
                }}
                className="p-2 bg-gray-950 hover:bg-gray-800 border border-gray-800 rounded-lg text-left text-gray-400 transition"
              >
                <div className="font-bold text-white">Customer</div>
                <div className="truncate">customer@gobeyond.com</div>
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthMode("password");
                  setLoginInput("admin@gobeyond.com");
                  setPassword("Admin@123");
                }}
                className="p-2 bg-gray-950 hover:bg-gray-800 border border-gray-800 rounded-lg text-left text-gray-400 transition"
              >
                <div className="font-bold text-rose-400">Super Admin</div>
                <div className="truncate">admin@gobeyond.com</div>
              </button>
            </div>
          </div>

          {/* Footer Navigation */}
          <div className="text-center text-xs text-gray-400 pt-2">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-bold text-brand-400 hover:text-brand-300 transition">
              Create an account
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}

