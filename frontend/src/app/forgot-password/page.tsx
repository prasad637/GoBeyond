"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  Lock,
  Mail,
  KeyRound,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  Eye,
  EyeOff
} from "lucide-react";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { forgotPassword, resetPassword } = useAuth();

  const [step, setStep] = useState<"request" | "reset" | "success">("request");
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [sandboxCode, setSandboxCode] = useState<string | null>(null);
  const [devNotice, setDevNotice] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleRequestOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailOrPhone.trim()) {
      setError("Please provide your registered email or mobile number.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await forgotPassword(emailOrPhone.trim());
      setMessage(res.message);
      if (res.sandbox_code) {
        setSandboxCode(res.sandbox_code);
        setDevNotice(res.dev_notice || "Development Sandbox Mode");
      }
      setStep("reset");
    } catch (err: any) {
      setError(err.message || "Failed to dispatch reset code.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp.trim()) {
      setError("Please enter the verification code.");
      return;
    }
    if (newPassword.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const res = await resetPassword(emailOrPhone.trim(), otp.trim(), newPassword);
      setMessage(res.message);
      setStep("success");
    } catch (err: any) {
      setError(err.message || "Failed to reset password. Check your verification code.");
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
          Reset Account Password
        </h2>
        <p className="mt-1 text-center text-xs text-gray-400">
          Recover your Go Beyond account securely via OTP
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-gray-900/90 backdrop-blur-xl py-8 px-6 shadow-2xl rounded-3xl border border-gray-800 space-y-6">

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === "request" && (
            <form onSubmit={handleRequestOtp} className="space-y-4">
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
                    value={emailOrPhone}
                    onChange={(e) => setEmailOrPhone(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !emailOrPhone.trim()}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <span>{loading ? "Sending Code..." : "Send Reset Code"}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

          {step === "reset" && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              {sandboxCode && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs space-y-1">
                  <div className="flex items-center space-x-1.5 text-amber-400 font-bold text-[11px]">
                    <KeyRound className="w-3.5 h-3.5" />
                    <span>DEVELOPMENT SANDBOX CODE</span>
                  </div>
                  <p className="text-gray-300 font-mono text-base tracking-widest font-black">
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
                    Enter Verification Code
                  </label>
                  <button
                    type="button"
                    onClick={() => { setStep("request"); setOtp(""); }}
                    className="text-[11px] text-brand-400 hover:text-brand-300"
                  >
                    Change identity
                  </button>
                </div>
                <input
                  type="text"
                  required
                  maxLength={6}
                  placeholder="123456"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  className="w-full text-center tracking-widest text-lg py-2.5 bg-gray-950 border border-gray-800 rounded-xl font-mono text-white focus:outline-none focus:border-brand-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={6}
                    placeholder="Minimum 6 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
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

              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Confirm New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={6}
                    placeholder="Re-enter new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-10 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !otp.trim() || newPassword.length < 6}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <span>{loading ? "Updating Password..." : "Set New Password"}</span>
                <ShieldCheck className="w-4 h-4" />
              </button>
            </form>
          )}

          {step === "success" && (
            <div className="text-center space-y-4 py-4">
              <div className="w-14 h-14 bg-emerald-500/20 text-emerald-400 rounded-2xl flex items-center justify-center mx-auto border border-emerald-500/30">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <h3 className="text-base font-bold text-white">Password Updated!</h3>
              <p className="text-xs text-gray-400">{message}</p>
              <button
                onClick={() => router.push("/login")}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition"
              >
                Proceed to Sign In
              </button>
            </div>
          )}

          <div className="text-center text-xs text-gray-400 pt-2 border-t border-gray-800/80">
            Remember password?{" "}
            <Link href="/login" className="font-bold text-brand-400 hover:text-brand-300 transition">
              Back to Sign In
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}

