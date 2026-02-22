"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import {
  Shield, Heart, HeartPulse, Home, Car, Briefcase, Building2,
  Phone, Mail, MapPin, ChevronRight, Star, CheckCircle,
  ArrowRight, Clock, Users, Award, Menu, X, Quote
} from "lucide-react";
import "./landing.css";

/* ── Data ────────────────────────────────────────────────── */

const SERVICES = [
  {
    icon: Heart,
    title: "Life Insurance",
    desc: "Secure your family's future with comprehensive life coverage plans tailored to your needs.",
  },
  {
    icon: HeartPulse,
    title: "Health Insurance",
    desc: "Complete medical coverage including hospitalization, surgeries, and preventive care benefits.",
  },
  {
    icon: Home,
    title: "Home Insurance",
    desc: "Protect your home and belongings against natural disasters, theft, and unexpected damages.",
  },
  {
    icon: Car,
    title: "Vehicle Insurance",
    desc: "Comprehensive auto coverage for accidents, theft, and third-party liability protection.",
  },
  {
    icon: Briefcase,
    title: "Business Insurance",
    desc: "Safeguard your enterprise with tailored commercial insurance and liability coverage.",
  },
  {
    icon: Building2,
    title: "Property Insurance",
    desc: "Full protection for commercial and residential properties against all potential risks.",
  },
];

const REASONS = [
  {
    icon: Shield,
    title: "Comprehensive Coverage",
    desc: "Wide range of insurance products covering every aspect of your life and business.",
  },
  {
    icon: Clock,
    title: "Fast Claims Processing",
    desc: "AI-powered claims processing ensures quick turnaround with transparent status tracking.",
  },
  {
    icon: Users,
    title: "Dedicated Support Team",
    desc: "24/7 expert support team ready to assist you with any queries or claims assistance.",
  },
  {
    icon: Award,
    title: "Award Winning Service",
    desc: "Recognized industry leader with multiple awards for customer satisfaction and innovation.",
  },
];

const TEAM_MEMBERS = [
  {
    name: "Rajesh Sharma",
    role: "Chief Executive Officer",
    image: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=400&h=400&fit=crop&crop=face&q=80",
  },
  {
    name: "Priya Patel",
    role: "Head of Claims",
    image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&h=400&fit=crop&crop=face&q=80",
  },
  {
    name: "Amit Verma",
    role: "Lead AI Engineer",
    image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&h=400&fit=crop&crop=face&q=80",
  },
  {
    name: "Sneha Reddy",
    role: "Compliance Director",
    image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=400&h=400&fit=crop&crop=face&q=80",
  },
];

const TESTIMONIALS = [
  {
    name: "Vikram Malhotra",
    position: "Business Owner",
    text: "InsureFlow transformed our claims process. What used to take weeks now gets resolved in days. The AI fraud detection gives us complete confidence.",
    avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=face&q=80",
  },
  {
    name: "Ananya Singh",
    position: "HR Manager",
    text: "The health insurance claims for our employees are processed seamlessly. The transparency and real-time tracking features are exceptional.",
    avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=face&q=80",
  },
  {
    name: "Rahul Kapoor",
    position: "Family Policyholder",
    text: "After my car accident, the claim was filed and processed within 48 hours. The OCR document scanning made uploading paperwork effortless.",
    avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=face&q=80",
  },
];

const LP_STATS = [
  { value: 5000, suffix: "+", label: "Happy Clients" },
  { value: 12000, suffix: "+", label: "Claims Processed" },
  { value: 98, suffix: "%", label: "Satisfaction Rate" },
  { value: 50, suffix: "+", label: "Team Members" },
];

/* ── Animated Counter Hook ───────────────────────────────── */

function useCountUp(target: number, duration = 2000, shouldStart = false) {
  const [count, setCount] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (!shouldStart || started.current) return;
    started.current = true;
    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [shouldStart, target, duration]);

  return count;
}

/* ── Counter Card Component ──────────────────────────────── */

function StatCard({ stat, inView }: { stat: typeof LP_STATS[0]; inView: boolean }) {
  const count = useCountUp(stat.value, 2000, inView);
  return (
    <div className="lp-stat-card">
      <div className="lp-stat-value">
        {count.toLocaleString()}{stat.suffix}
      </div>
      <div className="lp-stat-label">{stat.label}</div>
    </div>
  );
}

/* ── Main Page Component ─────────────────────────────────── */

export default function HomePage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [statsInView, setStatsInView] = useState(false);
  const statsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setStatsInView(true); },
      { threshold: 0.3 }
    );
    if (statsRef.current) observer.observe(statsRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="landing-page">

      {/* ── Top Bar ──────────────────────────────────────── */}
      <div className="lp-topbar">
        <div className="lp-topbar-inner">
          <div style={{ display: "flex", gap: 24 }}>
            <a href="mailto:contact@insureflow.in">
              <Mail size={14} /> contact@insureflow.in
            </a>
            <a href="tel:+911234567890">
              <Phone size={14} /> +91 123 456 7890
            </a>
          </div>
          <div style={{ display: "flex", gap: 16, fontSize: "0.75rem" }}>
            <Link href="/login" style={{ color: "rgba(255,255,255,0.7)", textDecoration: "none" }}>Sign In</Link>
            <span style={{ color: "rgba(255,255,255,0.3)" }}>|</span>
            <Link href="/register" style={{ color: "rgba(255,255,255,0.7)", textDecoration: "none" }}>Register</Link>
          </div>
        </div>
      </div>

      {/* ── Navbar ───────────────────────────────────────── */}
      <nav className="lp-navbar">
        <div className="lp-navbar-inner">
          <Link href="/" className="lp-logo">
            <div className="lp-logo-icon">
              <Shield size={22} />
            </div>
            InsureFlow
          </Link>

          <ul className="lp-nav-links">
            <li><a href="#home" className="active">Home</a></li>
            <li><a href="#services">Services</a></li>
            <li><a href="#about">About</a></li>
            <li><a href="#team">Team</a></li>
            <li><a href="#testimonials">Reviews</a></li>
            <li><a href="#contact">Contact</a></li>
          </ul>

          <div className="lp-nav-actions">
            <Link href="/login" className="lp-btn lp-btn-outline lp-btn-sm">Sign In</Link>
            <Link href="/register" className="lp-btn lp-btn-primary lp-btn-sm">Get Started</Link>
          </div>

          <button
            className="lp-mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div style={{
            background: "white",
            borderTop: "1px solid #e2e8f0",
            padding: "16px 24px",
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}>
            <a href="#home" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>Home</a>
            <a href="#services" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>Services</a>
            <a href="#about" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>About</a>
            <a href="#team" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>Team</a>
            <a href="#testimonials" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>Reviews</a>
            <a href="#contact" onClick={() => setMobileMenuOpen(false)} style={{ color: "#1e293b", textDecoration: "none", fontWeight: 500, padding: "8px 0" }}>Contact</a>
            <div style={{ display: "flex", gap: 8, paddingTop: 8 }}>
              <Link href="/login" className="lp-btn lp-btn-outline lp-btn-sm" style={{ flex: 1, justifyContent: "center" }}>Sign In</Link>
              <Link href="/register" className="lp-btn lp-btn-primary lp-btn-sm" style={{ flex: 1, justifyContent: "center" }}>Get Started</Link>
            </div>
          </div>
        )}
      </nav>

      {/* ── Hero Section ─────────────────────────────────── */}
      <section id="home" className="lp-hero">
        <div className="lp-hero-bg">
          <img
            src="https://images.unsplash.com/photo-1581579438747-1dc8d17bbce4?w=1920&q=80"
            alt="Happy family protected by insurance"
            loading="eager"
          />
        </div>
        <div className="lp-hero-overlay" />
        <div className="lp-hero-content">
          <div className="lp-hero-tag lp-animate">
            <span className="lp-hero-tag-dot" />
            Trusted by 5,000+ Policyholders
          </div>
          <h1 className="lp-animate lp-animate-delay-1">
            Insurance Creates<br />
            Wealth <span>For Everyone</span>
          </h1>
          <p className="lp-hero-desc lp-animate lp-animate-delay-2">
            Comprehensive insurance solutions powered by intelligent claims processing.
            Protect what matters most with fast, transparent, and AI-assisted coverage
            that puts you in control.
          </p>
          <div className="lp-hero-btns lp-animate lp-animate-delay-3">
            <Link href="/register" className="lp-btn lp-btn-primary">
              Get Started <ArrowRight size={18} />
            </Link>
            <Link href="#services" className="lp-btn lp-btn-white">
              Explore Services
            </Link>
          </div>
        </div>
      </section>

      {/* ── Services Section ─────────────────────────────── */}
      <section id="services" className="lp-section">
        <div className="lp-container">
          <div className="lp-section-header">
            <div className="lp-section-tag">Our Services</div>
            <h2 className="lp-section-title">We Provide Professional Insurance Services</h2>
            <p className="lp-section-desc">
              From life and health to property and business — our comprehensive insurance
              plans are designed to give you complete peace of mind.
            </p>
          </div>
          <div className="lp-services-grid">
            {SERVICES.map((s, i) => (
              <div key={s.title} className={`lp-service-card lp-animate lp-animate-delay-${i + 1}`}>
                <div className="lp-service-icon">
                  <s.icon size={28} />
                </div>
                <div className="lp-service-title">{s.title}</div>
                <div className="lp-service-desc">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── About / Experience Section ────────────────────── */}
      <section id="about" className="lp-section lp-section-alt">
        <div className="lp-container">
          <div className="lp-about-grid">
            <div>
              <div className="lp-experience-badge">
                <span className="number">25</span>
                <span className="label">Years Exp.</span>
              </div>
              <h2 className="lp-about-title">
                We&apos;re Here To Assist You With Exploring Protection
              </h2>
              <p className="lp-about-desc">
                With over two decades of experience in the insurance industry, we combine
                deep domain expertise with cutting-edge AI technology to deliver claims
                processing that is faster, more accurate, and completely transparent.
                Our platform ensures every claim is handled with care and precision.
              </p>
              <div className="lp-features-list">
                <div className="lp-feature-item">
                  <div className="lp-feature-check">
                    <CheckCircle size={14} />
                  </div>
                  Flexible Insurance Plans
                </div>
                <div className="lp-feature-item">
                  <div className="lp-feature-check">
                    <CheckCircle size={14} />
                  </div>
                  Money Back Guarantee
                </div>
              </div>
              <div className="lp-features-list">
                <div className="lp-feature-item">
                  <div className="lp-feature-check">
                    <CheckCircle size={14} />
                  </div>
                  AI-Powered Processing
                </div>
                <div className="lp-feature-item">
                  <div className="lp-feature-check">
                    <CheckCircle size={14} />
                  </div>
                  24/7 Claim Support
                </div>
              </div>
              <a href="tel:+911234567890" className="lp-phone-cta">
                <div className="lp-phone-icon">
                  <Phone size={18} />
                </div>
                Call Us: +91 123 456 7890
              </a>
            </div>
            <div className="lp-about-image">
              <img
                src="https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=800&q=80"
                alt="Professional insurance consultation"
                loading="lazy"
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Why Choose Us ────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-container">
          <div className="lp-reasons-grid">
            <div className="lp-reasons-image">
              <img
                src="https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=800&q=80"
                alt="Insurance professional"
                loading="lazy"
              />
            </div>
            <div>
              <div className="lp-section-tag" style={{ justifyContent: "flex-start" }}>Why Choose Us</div>
              <h2 className="lp-section-title" style={{ textAlign: "left" }}>
                Few Reasons Why People Choose Us
              </h2>
              <p style={{ color: "#64748b", marginBottom: 32, lineHeight: 1.7 }}>
                We are committed to providing the best insurance experience with modern technology,
                expert guidance, and unwavering support for all our policyholders.
              </p>
              {REASONS.map((r) => (
                <div key={r.title} className="lp-reason-item">
                  <div className="lp-reason-icon">
                    <r.icon size={22} />
                  </div>
                  <div>
                    <div className="lp-reason-title">{r.title}</div>
                    <div className="lp-reason-desc">{r.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Stats Counter ────────────────────────────────── */}
      <section className="lp-stats" ref={statsRef}>
        <div className="lp-stats-inner">
          <div className="lp-stats-header">
            <h2>For Individuals And Organizations</h2>
            <p>
              Trusted by thousands of policyholders and businesses across India
              for reliable insurance coverage and fast claims resolution.
            </p>
          </div>
          <div className="lp-stats-grid">
            {LP_STATS.map((stat) => (
              <StatCard key={stat.label} stat={stat} inView={statsInView} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Award Section ────────────────────────────────── */}
      <section className="lp-section lp-section-alt">
        <div className="lp-container">
          <div className="lp-award-grid">
            <div>
              <div className="lp-award-tag">
                <Award size={14} /> Award Winning
              </div>
              <h2 className="lp-award-title">
                We&apos;re An Award Winning Insurance Company
              </h2>
              <p className="lp-award-desc">
                Recognized for excellence in customer service, innovation in claims processing,
                and commitment to policyholder satisfaction. Our AI-powered platform has been
                acknowledged by leading industry bodies for transforming the insurance landscape.
              </p>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <Link href="/register" className="lp-btn lp-btn-primary">
                  Get Started <ArrowRight size={16} />
                </Link>
                <a href="tel:+911234567890" className="lp-btn lp-btn-outline">
                  <Phone size={16} /> +91 123 456 7890
                </a>
              </div>
            </div>
            <div className="lp-award-image">
              <img
                src="https://images.unsplash.com/photo-1521737711867-e3b97375f902?w=800&q=80"
                alt="Award winning insurance team"
                loading="lazy"
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Team Section ─────────────────────────────────── */}
      <section id="team" className="lp-section">
        <div className="lp-container">
          <div className="lp-section-header">
            <div className="lp-section-tag">Our Team</div>
            <h2 className="lp-section-title">Meet Our Professional Team Members</h2>
            <p className="lp-section-desc">
              Our dedicated team of insurance and technology experts works tirelessly to
              deliver the best experience for every policyholder.
            </p>
          </div>
          <div className="lp-team-grid">
            {TEAM_MEMBERS.map((m) => (
              <div key={m.name} className="lp-team-card">
                <img
                  src={m.image}
                  alt={m.name}
                  className="lp-team-img"
                  loading="lazy"
                />
                <div className="lp-team-info">
                  <div className="lp-team-name">{m.name}</div>
                  <div className="lp-team-role">{m.role}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ─────────────────────────────────── */}
      <section id="testimonials" className="lp-section lp-section-alt">
        <div className="lp-container">
          <div className="lp-section-header">
            <div className="lp-section-tag">Testimonials</div>
            <h2 className="lp-section-title">What They Say About Our Insurance</h2>
            <p className="lp-section-desc">
              Hear from our satisfied policyholders about their experience with InsureFlow.
            </p>
          </div>
          <div className="lp-testimonials-grid">
            {TESTIMONIALS.map((t) => (
              <div key={t.name} className="lp-testimonial-card">
                <Quote size={32} className="lp-quote-icon" />
                <div className="lp-testimonial-stars">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} size={16} fill="#f59e0b" stroke="#f59e0b" />
                  ))}
                </div>
                <div className="lp-testimonial-text">&ldquo;{t.text}&rdquo;</div>
                <div className="lp-testimonial-author">
                  <img
                    src={t.avatar}
                    alt={t.name}
                    className="lp-testimonial-avatar"
                    loading="lazy"
                  />
                  <div>
                    <div className="lp-testimonial-name">{t.name}</div>
                    <div className="lp-testimonial-position">{t.position}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA Banner ───────────────────────────────────── */}
      <section className="lp-cta-banner">
        <div className="lp-container">
          <h2>Ready to Secure Your Future?</h2>
          <p>
            Join thousands of satisfied policyholders. Register today and experience
            insurance the modern way.
          </p>
          <div className="lp-cta-banner-btns">
            <Link href="/register" className="lp-btn lp-btn-white">
              Create Free Account <ArrowRight size={16} />
            </Link>
            <Link href="/login" className="lp-btn lp-btn-outline" style={{ color: "white", borderColor: "rgba(255,255,255,0.4)" }}>
              Sign In to Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer id="contact" className="lp-footer">
        <div className="lp-footer-grid">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 8,
                background: "#1a56db", display: "flex",
                alignItems: "center", justifyContent: "center", color: "white",
              }}>
                <Shield size={22} />
              </div>
              <span style={{ fontWeight: 800, fontSize: "1.375rem", color: "white" }}>InsureFlow</span>
            </div>
            <p className="lp-footer-about">
              InsureFlow is a modern insurance claims intelligence platform combining
              AI-powered fraud detection, OCR document processing, and full regulatory
              compliance. Built for the future of insurance.
            </p>
          </div>

          <div>
            <div className="lp-footer-heading">Quick Links</div>
            <ul className="lp-footer-links">
              <li><a href="#home"><ChevronRight size={12} /> Home</a></li>
              <li><a href="#services"><ChevronRight size={12} /> Services</a></li>
              <li><a href="#about"><ChevronRight size={12} /> About Us</a></li>
              <li><a href="#team"><ChevronRight size={12} /> Our Team</a></li>
              <li><a href="#testimonials"><ChevronRight size={12} /> Testimonials</a></li>
            </ul>
          </div>

          <div>
            <div className="lp-footer-heading">Services</div>
            <ul className="lp-footer-links">
              <li><a href="#services"><ChevronRight size={12} /> Life Insurance</a></li>
              <li><a href="#services"><ChevronRight size={12} /> Health Insurance</a></li>
              <li><a href="#services"><ChevronRight size={12} /> Home Insurance</a></li>
              <li><a href="#services"><ChevronRight size={12} /> Vehicle Insurance</a></li>
              <li><a href="#services"><ChevronRight size={12} /> Business Insurance</a></li>
            </ul>
          </div>

          <div>
            <div className="lp-footer-heading">Contact Us</div>
            <div className="lp-footer-contact-item">
              <div className="lp-footer-contact-icon"><MapPin size={16} /></div>
              <div>123 Insurance Plaza,<br />Mumbai, Maharashtra 400001</div>
            </div>
            <div className="lp-footer-contact-item">
              <div className="lp-footer-contact-icon"><Phone size={16} /></div>
              <div>+91 123 456 7890</div>
            </div>
            <div className="lp-footer-contact-item">
              <div className="lp-footer-contact-icon"><Mail size={16} /></div>
              <div>contact@insureflow.in</div>
            </div>
          </div>
        </div>

        <div className="lp-footer-bottom">
          <span>&copy; 2026 InsureFlow. All rights reserved.</span>
          <div className="lp-footer-bottom-links">
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms of Service</Link>
          </div>
        </div>
      </footer>

    </div>
  );
}
