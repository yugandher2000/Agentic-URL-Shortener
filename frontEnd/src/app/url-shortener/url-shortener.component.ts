import { Component, signal, computed } from '@angular/core';
import { UrlShortenerService } from './url-shortener.service';

interface RecentLink {
  shortCode: string;
  shortUrl: string;
  originalUrl: string;
  clickCount: number;
  createdAt: string;
}

@Component({
  selector: 'app-url-shortener',
  standalone: true,
  imports: [],
  templateUrl: './url-shortener.component.html',
  styleUrl: './url-shortener.component.scss'
})
export class UrlShortenerComponent {
  longUrl     = signal('');
  loading     = signal(false);
  error       = signal('');
  copied      = signal(false);
  recentLinks = signal<RecentLink[]>([]);

  totalClicks = computed(() =>
    this.recentLinks().reduce((sum, l) => sum + l.clickCount, 0)
  );

  activeToday = computed(() => {
    const today = new Date().toDateString();
    return this.recentLinks().filter(l =>
      new Date(l.createdAt).toDateString() === today
    ).length;
  });

  constructor(private svc: UrlShortenerService) {}

  shorten(): void {
    const url = this.longUrl().trim();
    if (!url) return;

    this.loading.set(true);
    this.error.set('');

    this.svc.shorten(url).subscribe({
      next: res => {
        this.loading.set(false);
        this.longUrl.set('');
        const code = res.shortUrl.split('/').pop() ?? '';
        this.svc.analytics(code).subscribe({
          next: a => {
            this.recentLinks.update(links => [
              { shortCode: a.shortCode, shortUrl: a.shortUrl, originalUrl: a.originalUrl, clickCount: a.clickCount, createdAt: a.createdAt },
              ...links.filter(l => l.shortCode !== a.shortCode)
            ]);
          }
        });
      },
      error: err => {
        const msg = err?.error?.longUrl ?? err?.error?.error ?? 'Something went wrong.';
        this.error.set(msg);
        this.loading.set(false);
      }
    });
  }

  copyLink(url: string): void {
    navigator.clipboard.writeText(url).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  removeLink(shortCode: string): void {
    this.recentLinks.update(links => links.filter(l => l.shortCode !== shortCode));
  }

  truncate(url: string, max = 55): string {
    return url.length > max ? url.slice(0, max) + '…' : url;
  }
}
