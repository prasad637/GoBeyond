"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  User as UserIcon,
  Mail,
  Smartphone,
  Lock,
  Eye,
  EyeOff,
  Building2,
  MapPin,
  ArrowRight,
  AlertCircle,
  CheckCircle2
} from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [role, setRole] = useState("customer");
  const [localityId, setLocalityId] = useState<number | undefined>(undefined);
  const [localities, setLocalities] = useState<any[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch Hyderabad localities from Module 1 database
    apiRequest<any[]>("/locations/localities?city_slug=hyderabad")
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setLocalities(data);
          setLocalityId(data[0].id);
        }
      })
      .catch(() => {});
  }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (phone.length < 10) {
      setError("Please provide a valid 10-digit mobile number.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const res = await register({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        password,
        role,
        locality_id: localityId,
      });

      if (res.role.startsWith("partner_")) {
        router.push("/partner");
      } else {
        router.push("/profile");
      }
    } catch (err: any) {
      setError(err.message || "Registration failed. Email or mobile may already be registered.");
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
          Create Your Go Beyond Account
        </h2>
        <p className="mt-1 text-center text-xs text-gray-400">
          Join thousands experiencing Hyderabad&apos;s entertainment ecosystem.
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

          <form onSubmit={handleRegister} className="space-y-4">
            
            {/* Account Type / Role */}
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                Account Type
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
              >
                <option value="customer">Consumer (Book & Experience)</option>
                <option value="partner_restaurant">Dining Partner (Restaurant / Pub / Cafe)</option>
                <option value="partner_cinema">Cinema Operator (Multiplex / Theatre)</option>
                <option value="partner_event">Event Organizer (Concerts / Nightlife / Comedy)</option>
                <option value="partner_sports">Sports Venue / Turf Operator</option>
              </select>
            </div>

            {/* Full Name */}
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  placeholder="John Doe"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                />
              </div>
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-500">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  required
                  placeholder="john@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white placeholder-gray-600 focus:outline-none focus:border-brand-500 transition"
                />
              </div>
            </div>

            {/* Mobile Phone */}
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

            {/* Locality in Hyderabad */}
            {localities.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5 flex items-center space-x-1">
                  <MapPin className="w-3.5 h-3.5 text-brand-500" />
                  <span>Home Locality (Hyderabad)</span>
                </label>
                <select
                  value={localityId}
                  onChange={(e) => setLocalityId(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
                >
                  {localities.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                Password
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
              className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50 pt-3"
            >
              <span>{loading ? "Creating Account..." : "Create Account"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Footer Navigation */}
          <div className="text-center text-xs text-gray-400 pt-2 border-t border-gray-800/80">
            Already have an account?{" "}
            <Link href="/login" className="font-bold text-brand-400 hover:text-brand-300 transition">
              Sign In
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}

