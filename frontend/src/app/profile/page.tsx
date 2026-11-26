"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  User as UserIcon,
  Mail,
  Phone,
  MapPin,
  Bell,
  Save,
  CheckCircle2,
  AlertCircle,
  LogOut,
  ShieldCheck,
  Smartphone,
  Trash2,
  Activity,
  Layers,
  Sparkles
} from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const { user, logout, logoutAll, deactivateAccount, updateProfile, refreshUser, openAuthModal } = useAuth();

  const [fullName, setFullName] = useState("");
  const [preferredLang, setPreferredLang] = useState("English");
  const [bio, setBio] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [localityId, setLocalityId] = useState<number | null>(null);
  const [localities, setLocalities] = useState<any[]>([]);
  const [localitiesLoading, setLocalitiesLoading] = useState(true);
  const [notifications, setNotifications] = useState<any[]>([]);

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDeactivateModal, setShowDeactivateModal] = useState(false);

  useEffect(() => {
    // Fetch Hyderabad localities from Module 1 database using city_slug query param
    setLocalitiesLoading(true);
    apiRequest<any[]>("/locations/localities?city_slug=hyderabad")
      .then((data) => {
        if (Array.isArray(data)) {
          setLocalities(data);
        }
      })
      .catch(() => {})
      .finally(() => setLocalitiesLoading(false));
  }, []);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setPreferredLang(user.preferred_language || "English");
      setBio(user.bio || "");
      setAvatarUrl(user.avatar_url || "");
      setEmergencyPhone(user.emergency_phone || "");
      setLocalityId(user.locality_id ?? null);

      // Fetch user notifications
      apiRequest<any>("/notifications/")
        .then((data) => {
          const items = Array.isArray(data)
            ? data
            : Array.isArray(data?.items)
            ? data.items
            : [];
          setNotifications(items);
        })
        .catch(() => {});
    }
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6 text-white">
        <UserIcon className="w-16 h-16 text-brand-500 mb-4" />
        <h2 className="text-2xl font-bold">Please sign in to view your profile</h2>
        <div className="flex space-x-3 mt-4">
          <Link
            href="/login"
            className="px-6 py-2.5 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs transition"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="px-6 py-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-800 font-bold rounded-xl text-xs transition"
          >
            Create Account
          </Link>
        </div>
      </div>
    );
  }

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await updateProfile({
        full_name: fullName.trim(),
        preferred_language: preferredLang,
        bio: bio.trim(),
        avatar_url: avatarUrl.trim(),
        emergency_phone: emergencyPhone.trim(),
        locality_id: localityId,
      });
      setSuccess("Profile details updated successfully!");
    } catch (err: any) {
      setError(err.message || "Failed to update profile.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogoutAll = async () => {
    if (confirm("Are you sure you want to log out of all active devices? You will need to sign in again.")) {
      try {
        await logoutAll();
        router.push("/login");
      } catch (err: any) {
        setError(err.message || "Failed to terminate sessions.");
      }
    }
  };

  const handleDeactivate = async () => {
    try {
      await deactivateAccount();
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Failed to deactivate account.");
      setShowDeactivateModal(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto space-y-10">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-gray-800 gap-4">
        <div>
          <h1 className="text-3xl font-extrabold flex items-center space-x-3">
            <UserIcon className="w-7 h-7 text-brand-500" />
            <span>My Account Profile</span>
          </h1>
          <p className="text-gray-400 text-xs mt-1">Manage personal details, locality discovery preferences, and active sessions</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={logout}
            className="px-4 py-2 bg-gray-900 hover:bg-red-500/20 text-red-400 border border-gray-800 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
          <button
            onClick={handleLogoutAll}
            className="px-4 py-2 bg-gray-900 hover:bg-amber-500/20 text-amber-400 border border-gray-800 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5"
          >
            <Layers className="w-4 h-4" />
            <span>Sign Out All Devices</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Left Card: Account Overview */}
        <div className="space-y-6">
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-3xl space-y-5 text-center">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={user.full_name}
                className="w-20 h-20 rounded-2xl object-cover mx-auto shadow-xl shadow-brand-500/20 border border-brand-500/30"
              />
            ) : (
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-brand-600 to-rose-400 flex items-center justify-center text-3xl font-extrabold text-white uppercase mx-auto shadow-xl shadow-brand-500/20">
                {user.full_name?.charAt(0) || "U"}
              </div>
            )}

            <div>
              <h2 className="text-lg font-bold text-white">{user.full_name}</h2>
              <p className="text-xs text-gray-400">{user.email}</p>
            </div>

            {/* Account Status Badge */}
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Account Status: {user.account_status || "ACTIVE"}</span>
            </div>

            <div className="p-3 bg-gray-950 rounded-xl text-xs space-y-2 text-left">
              <div className="flex items-center space-x-2 text-gray-400">
                <Phone className="w-3.5 h-3.5 text-gray-500" />
                <span>{user.phone}</span>
              </div>
              <div className="flex items-center space-x-2 text-gray-400">
                <MapPin className="w-3.5 h-3.5 text-gray-500" />
                <span>
                  {user.locality_name ? `${user.locality_name}, ` : ""}
                  {user.city_name || "Hyderabad"}
                </span>
              </div>
              <div className="flex items-center space-x-2 text-brand-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Role: {user.roles?.join(", ")}</span>
              </div>
            </div>

            {user.partner_id && (
              <div className="p-3 bg-brand-500/10 border border-brand-500/30 rounded-xl text-left">
                <span className="text-[10px] text-brand-400 font-bold uppercase tracking-wider block">Partner Portal</span>
                <p className="text-xs text-white mt-0.5">Verified {user.partner_type} Partner</p>
                <Link
                  href="/partner"
                  className="mt-2 block text-center py-1.5 bg-brand-600 hover:bg-brand-500 rounded-lg text-xs font-bold text-white transition"
                >
                  Open Partner Dashboard
                </Link>
              </div>
            )}
          </div>

          {/* Danger Zone */}
          <div className="p-6 bg-red-950/20 border border-red-900/30 rounded-3xl space-y-3">
            <h4 className="text-xs font-bold text-red-400 uppercase tracking-wider flex items-center space-x-1.5">
              <Trash2 className="w-4 h-4" />
              <span>Danger Zone</span>
            </h4>
            <p className="text-[11px] text-gray-400">
              Deactivating your account disables your access, revokes active sessions, and cancels pending activities.
            </p>
            <button
              onClick={() => setShowDeactivateModal(true)}
              className="w-full py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-xl text-xs font-bold transition"
            >
              Deactivate My Account
            </button>
          </div>
        </div>

        {/* Right Form: Edit Profile Details */}
        <div className="md:col-span-2 space-y-6">
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-3xl shadow-xl space-y-5">
            <h3 className="font-bold text-base text-white">Edit Profile Details</h3>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                <span>{success}</span>
              </div>
            )}

            <form onSubmit={handleUpdateProfile} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Full Name
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Avatar Image URL
                </label>
                <input
                  type="url"
                  placeholder="https://images.unsplash.com/photo-..."
                  value={avatarUrl}
                  onChange={(e) => setAvatarUrl(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
                />
              </div>

              <div>
                <label
                  htmlFor="profile-locality-select"
                  className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5 flex items-center space-x-1"
                >
                  <MapPin className="w-3.5 h-3.5 text-brand-500" />
                  <span>Selected Locality (Hyderabad)</span>
                </label>
                <select
                  id="profile-locality-select"
                  aria-label="Selected Locality (Hyderabad)"
                  disabled={localitiesLoading && localities.length === 0}
                  value={localityId != null ? String(localityId) : ""}
                  onChange={(e) => setLocalityId(e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition disabled:opacity-60"
                >
                  <option value="">All Hyderabad Localities</option>
                  {localities.map((loc) => (
                    <option key={loc.id} value={String(loc.id)}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                    Preferred Language
                  </label>
                  <select
                    value={preferredLang}
                    onChange={(e) => setPreferredLang(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
                  >
                    <option value="English">English</option>
                    <option value="Telugu">Telugu</option>
                    <option value="Hindi">Hindi</option>
                    <option value="Tamil">Tamil</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                    Emergency Contact Phone
                  </label>
                  <input
                    type="tel"
                    placeholder="Optional 10-digit phone"
                    value={emergencyPhone}
                    onChange={(e) => setEmergencyPhone(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">
                  Bio / Interests
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Cinephile, foodie, weekend badminton player"
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-gray-950 border border-gray-800 rounded-xl text-xs text-white focus:outline-none focus:border-brand-500 transition resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-brand-600 hover:bg-brand-500 font-bold rounded-xl text-xs text-white shadow-lg shadow-brand-500/20 transition flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                <span>{loading ? "Saving Changes..." : "Save Profile Details"}</span>
              </button>
            </form>
          </div>

          {/* Activity Notifications */}
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-3xl space-y-4">
            <h3 className="font-bold text-base text-white flex items-center space-x-2">
              <Bell className="w-4 h-4 text-brand-400" />
              <span>Recent Activity Notifications</span>
            </h3>

            {notifications.length === 0 ? (
              <p className="text-xs text-gray-500">No new notifications.</p>
            ) : (
              <div className="space-y-2.5">
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className="p-3 bg-gray-950 border border-gray-800 rounded-xl space-y-1 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white">{n.title}</span>
                      <span className="text-[10px] text-gray-500">{n.created_at}</span>
                    </div>
                    <p className="text-gray-400 text-[11px]">{n.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

      </div>

      {/* Account Deactivation Modal */}
      {showDeactivateModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-red-900/40 rounded-3xl p-6 max-w-md w-full space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-red-500/20 text-red-400 flex items-center justify-center mx-auto border border-red-500/30">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-bold text-white">Deactivate Your Account?</h3>
              <p className="text-xs text-gray-400 mt-1">
                Are you sure you want to deactivate your Go Beyond account? This action will immediately terminate all active sessions on all devices.
              </p>
            </div>
            <div className="flex space-x-3 pt-2">
              <button
                type="button"
                onClick={() => setShowDeactivateModal(false)}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-bold rounded-xl text-xs transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeactivate}
                className="flex-1 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl text-xs transition"
              >
                Yes, Deactivate
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
