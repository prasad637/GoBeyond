import React from "react";
import { Layers, QrCode, ShieldCheck, Zap } from "lucide-react";

const PILLARS = [
  {
    icon: Layers,
    eyebrow: "01",
    title: "Five Categories, One Destination",
    description:
      "Browse movies, restaurants, live events, sports venues, and recreational activities side by side.",
  },
  {
    icon: Zap,
    eyebrow: "02",
    title: "Real-Time Slot & Seat Selection",
    description:
      "Inspect live show timings, court availability, ticket tiers, and dining table zones before paying.",
  },
  {
    icon: ShieldCheck,
    eyebrow: "03",
    title: "Verified Booking Confirmation",
    description:
      "Protected server-side inventory holds and verified checkout state before issuing your pass.",
  },
  {
    icon: QrCode,
    eyebrow: "04",
    title: "Digital Gate Pass & Records",
    description:
      "Access confirmed bookings, QR gate passes, receipts, and notifications from one account.",
  },
];

export function WhyGoBeyondSection() {
  return (
    <section aria-labelledby="why-gobeyond-heading" className="py-2">
      <div className="mb-6 space-y-1.5">
        <div className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-champagne">
          Why GO BEYOND
        </div>
        <h2
          id="why-gobeyond-heading"
          className="font-display text-xl sm:text-2xl font-bold tracking-tight text-primary"
        >
          Designed Around How Hyderabad Goes Out
        </h2>
        <p className="text-xs sm:text-sm text-secondary max-w-2xl">
          Everything needed to discover experiences and hold confirmed passes cleanly without switching apps.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {PILLARS.map((pillar) => {
          const Icon = pillar.icon;
          return (
            <div
              key={pillar.title}
              className="p-5 rounded-xl bg-surface border border-subtle hover:border-strong transition-colors flex flex-col justify-between gap-4"
            >
              <div className="flex items-center justify-between">
                <span className="w-9 h-9 rounded-lg bg-surface-2 border border-subtle flex items-center justify-center text-brand-400">
                  <Icon className="w-4 h-4" aria-hidden="true" />
                </span>
                <span className="font-mono text-[11px] text-champagne/80 tracking-widest">
                  {pillar.eyebrow}
                </span>
              </div>

              <div className="space-y-1.5">
                <h3 className="font-display text-base font-bold text-primary tracking-tight">
                  {pillar.title}
                </h3>
                <p className="text-xs text-secondary leading-relaxed">
                  {pillar.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

