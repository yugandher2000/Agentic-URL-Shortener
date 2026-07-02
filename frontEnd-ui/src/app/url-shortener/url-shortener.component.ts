import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { UrlShortenerService, AnalyticsResponse } from './url-shortener.service';

@Component({
  selector: 'app-url-shortener',
  standalone: true,
  imports: [FormsModule, DatePipe],
  templateUrl: './url-shortener.component.html',
  styleUrl: './url-shortener.component.sass'
})
export class UrlShortenerComponent {
  longUrl  = signal('');
  shortUrl = signal('');
  loading  = signal(false);
  error    = signal('');
  copied   = signal(false);
  analytics = signal<AnalyticsResponse | null>(null);

  constructor(private svc: UrlShortenerService) {}

  shorten(): void {
    const url = this.longUrl().trim();
    if (!url) return;

    this.loading.set(true);
    this.error.set('');
    this.shortUrl.set('');
    this.analytics.set(null);

    this.svc.shorten(url).subscribe({
      next: res => {
        this.shortUrl.set(res.shortUrl);
        this.loading.set(false);
        // Fetch analytics for the code just created
        const code = res.shortUrl.split('/').pop() ?? '';
        this.svc.analytics(code).subscribe({ next: a => this.analytics.set(a) });
      },
      error: err => {
        const msg = err?.error?.longUrl ?? err?.error?.error ?? 'Something went wrong.';
        this.error.set(msg);
        this.loading.set(false);
      }
    });
  }

  copy(): void {
    navigator.clipboard.writeText(this.shortUrl()).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  reset(): void {
    this.longUrl.set('');
    this.shortUrl.set('');
    this.error.set('');
    this.analytics.set(null);
  }
}
