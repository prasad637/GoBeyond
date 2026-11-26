"use client";

import React from "react";
import Link from "next/link";
import { Compass, Heart, Shield, HelpCircle, MapPin } from "lucide-react";
import { useLocation } from "@/context/LocationContext";

export default function Footer() {
  const { selectedCity } = useLocation();
  const activeCity = selectedCity || "Hyderabad";

  return (
    <footer className="w-full bg-surface/50 border-t border-subtle text-secondary text-xs">
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-8">
          {/* Brand Info */}
          <div className="sm:col-span-2 space-y-4">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-xl bg-brand-500 flex items-center justify-center text-white shadow-brand-sm">
                <Compass className="w-5 h-5" />
              </span>
              <span className="font-display font-extrabold text-xl text-primary tracking-wider">
                GO<span className="text-brand-500">BEYOND</span>
              </span>
            </div>
            <p className="text-secondary leading-relaxed pr-4 text-xs max-w-md">
              {activeCity}&rsquo;s curated entertainment, dining, and live-experience
              booking destination. Discover Dolby Atmos cinemas, reserve top tables,
              book live concerts, and reserve sports turfs in one unified platform.
            </p>
            <div className="flex items-center gap-2 text-muted text-xs">
              <MapPin className="w-3.5 h-3.5 text-brand-500 shrink-0" />
              <span>{activeCity}, Telangana, India</span>
            </div>
          </div>

          {/* Categories */}
          <div className="space-y-3">
            <h4 className="font-display font-semibold text-primary text-sm">
              Experiences
            </h4>
            <ul className="space-y-2">
              <li>
                <Link href="/movies" className="hover:text-brand-400 transition-colors">
                  Latest Movies &amp; Cinemas
                </Link>
              </li>
              <li>
                <Link href="/dining" className="hover:text-brand-400 transition-colors">
                  Fine Dining &amp; Cafes
                </Link>
              </li>
              <li>
                <Link href="/events" className="hover:text-brand-400 transition-colors">
                  Concerts &amp; Comedy Shows
                </Link>
              </li>
              <li>
                <Link href="/sports" className="hover:text-brand-400 transition-colors">
                  Badminton &amp; Turf Football
                </Link>
              </li>
              <li>
                <Link href="/activities" className="hover:text-brand-400 transition-colors">
                  Go-Karting &amp; Arcades
                </Link>
              </li>
            </ul>
          </div>

          {/* Partners & Admin */}
          <div className="space-y-3">
            <h4 className="font-display font-semibold text-primary text-sm">
              For Partners
            </h4>
            <ul className="space-y-2">
              <li>
                <Link href="/partner" className="hover:text-console-400 transition-colors">
                  Partner Portal Login
                </Link>
              </li>
              <li>
                <Link
                  href="/partner?tab=register"
                  className="hover:text-console-400 transition-colors"
                >
                  List Your Restaurant
                </Link>
              </li>
              <li>
                <Link
                  href="/partner?tab=register"
                  className="hover:text-console-400 transition-colors"
                >
                  Host an Event
                </Link>
              </li>
              <li>
                <Link
                  href="/partner?tab=register"
                  className="hover:text-console-400 transition-colors"
                >
                  Register Sports Turf
                </Link>
              </li>
              <li>
                <Link href="/admin" className="hover:text-amber-300 transition-colors">
                  Super Admin Console
                </Link>
              </li>
            </ul>
          </div>

          {/* Trust & Legal */}
          <div className="space-y-3">
            <h4 className="font-display font-semibold text-primary text-sm">
              Security &amp; Trust
            </h4>
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>256-Bit SSL Encryption</span>
              </li>
              <li className="flex items-center gap-2">
                <Shield className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>Verified Razorpay Gateway</span>
              </li>
              <li className="flex items-center gap-2">
                <HelpCircle className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                <span>24×7 Customer Support</span>
              </li>
              <li>
                <span className="text-muted">Terms of Service &amp; Privacy</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-subtle flex flex-col sm:flex-row items-center justify-between text-xs text-muted gap-3">
          <p>© 2026 GO BEYOND Platforms Pvt. Ltd. All rights reserved.</p>
          <p className="flex items-center gap-1.5">
            <span>Crafted with</span>
            <Heart className="w-3.5 h-3.5 text-brand-500 fill-brand-500" />
            <span>for {activeCity} &amp; beyond.</span>
          </p>
        </div>
      </div>
    </footer>
  );
}
