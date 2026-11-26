"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  Smartphone,
  ShieldCheck,
  KeyRound,
  AlertCircle,
  ArrowRight,
  RefreshCw
} from "lucide-react";

export default function VerifyOtpPage() {
  const router = useRouter();
  const { requestOtp, verifyOtp } = useAuth();

  const [phone, setPhone] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [sandboxCode, setSandboxCode] = useState<string | null>(null);
  const [devNotice, setDevNotice] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone || phone.length < 10) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      const res = await requestOtp(phone.trim(), "login");
      setOtpSent(true);
      setMessage(res.message);
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

  const handleVerify = async (e: React.FormEvent) => {
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
      setError(err.message || "Invalid or expired verification code.");
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
          Mobile OTP Verification
        </h2>
        <p className="mt-1 text-center text-xs text-gray-400">
          Fast, passwordless sign in via secure SMS / WhatsApp code
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

          {message && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 flex-shrink-0" />
              <span>{message}</span>
            </div>
          )}

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
                <span>{loading ? "Sending..." : "Send Verification Code"}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerify} className="space-y-4">
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
                    Enter 6-Digit OTP
                  </label>
                  <button
                    type="button"
                    onClick={() => { setOtpSent(false); setOtpCode(""); }}
                    className="text-[11px] text-brand-400 hover:text-brand-300"
                  >
                    Change mobile number
                  </button>
                </div>
                <input
                  type="text"
                  required
                  maxLength={6}
                  placeholder="123456"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="w-full text-center tracking-widest text-xl py-3 bg-gray-950 border border-gray-800 rounded-xl font-mono text-white focus:outline-none focus:border-brand-500 transition"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length < 4}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <span>{loading ? "Verifying..." : "Verify & Continue"}</span>
                <ShieldCheck className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={handleSendOtp}
                className="w-full text-center text-xs text-gray-500 hover:text-gray-300 flex items-center justify-center space-x-1 pt-2 transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Resend code</span>
              </button>
            </form>
          )}

          <div className="text-center text-xs text-gray-400 pt-2 border-t border-gray-800/80">
            Prefer password?{" "}
            <Link href="/login" className="font-bold text-brand-400 hover:text-brand-300 transition">
              Sign In with Password
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}

