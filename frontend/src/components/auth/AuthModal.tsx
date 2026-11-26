"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { X, Lock, Mail, Phone, User, CheckCircle2, AlertCircle, ArrowRight, Sparkles } from "lucide-react";

export default function AuthModal() {
  const { isAuthModalOpen, closeAuthModal, authModalInitialTab, login, register, requestOtp, verifyOtp } = useAuth();

  const [activeTab, setActiveTab] = useState<"login" | "otp" | "register" | "forgot">("login");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Form states
  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [regFullName, setRegFullName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPhone, setRegPhone] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regRole, setRegRole] = useState("customer");

  const [otpPhone, setOtpPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);

  useEffect(() => {
    if (authModalInitialTab === "register") setActiveTab("register");
    else if (authModalInitialTab === "otp") setActiveTab("otp");
    else setActiveTab("login");
    setError(null);
    setSuccess(null);
  }, [authModalInitialTab, isAuthModalOpen]);

  if (!isAuthModalOpen) return null;

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(loginIdentifier, loginPassword);
    } catch (err: any) {
      setError(err.message || "Failed to log in.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = async (email: string, pass: string) => {
    setError(null);
    setLoading(true);
    try {
      await login(email, pass);
    } catch (err: any) {
      setError(err.message || "Failed to log in.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({
        full_name: regFullName,
        email: regEmail,
        phone: regPhone,
        password: regPassword,
        role: regRole,
      });
    } catch (err: any) {
      setError(err.message || "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleSendOtp = async () => {
    if (!otpPhone || otpPhone.length < 10) {
      setError("Please provide a valid 10-digit mobile number.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await requestOtp(otpPhone, "login");
      setOtpSent(true);
      setSuccess(res.message);
      if (res.sandbox_code) {
        setOtpCode(res.sandbox_code);
      }
    } catch (err: any) {
      setError(err.message || "Failed to send OTP.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await verifyOtp(otpPhone, otpCode, "login");
    } catch (err: any) {
      setError(err.message || "Invalid OTP.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-lg bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden text-white">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-950/60">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-500 animate-pulse"></span>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-rose-100 to-brand-500 bg-clip-text text-transparent">
              GO BEYOND
            </span>
          </div>
          <button
            onClick={closeAuthModal}
            className="p-1 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-gray-800 bg-gray-900/50">
          <button
            onClick={() => { setActiveTab("login"); setError(null); }}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === "login"
                ? "border-brand-500 text-brand-400 bg-brand-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            Password Login
          </button>
          <button
            onClick={() => { setActiveTab("otp"); setError(null); }}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === "otp"
                ? "border-brand-500 text-brand-400 bg-brand-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            OTP Login
          </button>
          <button
            onClick={() => { setActiveTab("register"); setError(null); }}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition ${
              activeTab === "register"
                ? "border-brand-500 text-brand-400 bg-brand-500/10"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start space-x-2 text-red-400 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-start space-x-2 text-emerald-400 text-sm">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span>{success}</span>
            </div>
          )}

          {/* TAB 1: PASSWORD LOGIN */}
          {activeTab === "login" && (
            <div>
              <form onSubmit={handlePasswordLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                    Email or Mobile Number
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      required
                      placeholder="e.g. customer@gobeyond.com or 9876543210"
                      value={loginIdentifier}
                      onChange={(e) => setLoginIdentifier(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-gray-800/80 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                    <input
                      type="password"
                      required
                      placeholder="Enter your password"
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-gray-800/80 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 px-4 bg-gradient-to-r from-brand-600 to-rose-600 hover:from-brand-500 hover:to-rose-500 font-semibold rounded-xl text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
                >
                  {loading ? (
                    <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                  ) : (
                    <>
                      <span>Sign In to Experience</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              {/* Quick Demo Logins Section */}
              <div className="mt-6 pt-5 border-t border-gray-800">
                <div className="flex items-center space-x-1.5 mb-3 text-xs text-gray-400 uppercase tracking-wider">
                  <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                  <span>One-Click Demo Profiles</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <button
                    onClick={() => handleQuickLogin("admin@gobeyond.com", "Admin@123")}
                    className="p-2.5 bg-gray-800/80 hover:bg-gray-750 border border-gray-700 hover:border-brand-500/50 rounded-lg text-left transition"
                  >
                    <div className="font-semibold text-brand-400">Super Admin</div>
                    <div className="text-gray-400 truncate">admin@gobeyond.com</div>
                  </button>
                  <button
                    onClick={() => handleQuickLogin("customer@gobeyond.com", "Customer@123")}
                    className="p-2.5 bg-gray-800/80 hover:bg-gray-750 border border-gray-700 hover:border-brand-500/50 rounded-lg text-left transition"
                  >
                    <div className="font-semibold text-emerald-400">Customer</div>
                    <div className="text-gray-400 truncate">customer@gobeyond.com</div>
                  </button>
                  <button
                    onClick={() => handleQuickLogin("cinema.partner@gobeyond.com", "Partner@123")}
                    className="p-2.5 bg-gray-800/80 hover:bg-gray-750 border border-gray-700 hover:border-brand-500/50 rounded-lg text-left transition"
                  >
                    <div className="font-semibold text-purple-400">Cinema Partner</div>
                    <div className="text-gray-400 truncate">cinema.partner@gobeyond.com</div>
                  </button>
                  <button
                    onClick={() => handleQuickLogin("restaurant.partner@gobeyond.com", "Partner@123")}
                    className="p-2.5 bg-gray-800/80 hover:bg-gray-750 border border-gray-700 hover:border-brand-500/50 rounded-lg text-left transition"
                  >
                    <div className="font-semibold text-amber-400">Dining Partner</div>
                    <div className="text-gray-400 truncate">restaurant.partner@gobeyond.com</div>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: OTP LOGIN */}
          {activeTab === "otp" && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                  Mobile Number
                </label>
                <div className="flex space-x-2">
                  <div className="relative flex-1">
                    <Phone className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                    <input
                      type="tel"
                      placeholder="10-digit mobile number"
                      value={otpPhone}
                      onChange={(e) => setOtpPhone(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-gray-800/80 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSendOtp}
                    disabled={loading || !otpPhone}
                    className="px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-brand-400 font-semibold rounded-xl text-sm transition disabled:opacity-50"
                  >
                    {otpSent ? "Resend" : "Send OTP"}
                  </button>
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  Sandbox Mode active: Code is <span className="text-brand-400 font-mono font-bold">123456</span>
                </p>
              </div>

              {otpSent && (
                <form onSubmit={handleVerifyOtp} className="space-y-4 pt-2">
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1.5">
                      Enter 6-Digit OTP Code
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      placeholder="123456"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      className="w-full text-center tracking-widest text-xl font-mono py-2.5 bg-gray-800 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-brand-500 transition"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !otpCode}
                    className="w-full py-3 px-4 bg-gradient-to-r from-brand-600 to-rose-600 font-semibold rounded-xl text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                    ) : (
                      <>
                        <span>Verify & Sign In</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}

          {/* TAB 3: REGISTER */}
          {activeTab === "register" && (
            <form onSubmit={handleRegister} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <User className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Priya Reddy"
                    value={regFullName}
                    onChange={(e) => setRegFullName(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="email"
                    required
                    placeholder="priya@example.com"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Mobile Number
                </label>
                <div className="relative">
                  <Phone className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="tel"
                    required
                    placeholder="10-digit mobile number"
                    value={regPhone}
                    onChange={(e) => setRegPhone(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3 w-4 h-4 text-gray-400" />
                  <input
                    type="password"
                    required
                    minLength={6}
                    placeholder="Minimum 6 characters"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm placeholder-gray-500 focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1">
                  Account Type
                </label>
                <select
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-xl text-white text-sm focus:outline-none focus:border-brand-500 transition"
                >
                  <option value="customer">Customer (Explore & Book)</option>
                  <option value="partner_restaurant">Restaurant / Dining Partner</option>
                  <option value="partner_cinema">Cinema / Multiplex Partner</option>
                  <option value="partner_event">Live Event / Concert Organizer</option>
                  <option value="partner_sports">Sports Turf / Activity Partner</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-gradient-to-r from-brand-600 to-rose-600 font-semibold rounded-xl text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50 mt-2"
              >
                {loading ? (
                  <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                ) : (
                  <>
                    <span>Create Free Account</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

        </div>
      </div>
    </div>
  );
}

