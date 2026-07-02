import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

const API = 'http://localhost:8080';

export interface ShortenResponse {
  shortUrl: string;
}

export interface AnalyticsResponse {
  shortCode: string;
  shortUrl: string;
  originalUrl: string;
  clickCount: number;
  createdAt: string;
}

@Injectable({ providedIn: 'root' })
export class UrlShortenerService {
  constructor(private http: HttpClient) {}

  shorten(longUrl: string): Observable<ShortenResponse> {
    return this.http.post<ShortenResponse>(`${API}/api/shorten`, { longUrl });
  }

  analytics(shortCode: string): Observable<AnalyticsResponse> {
    return this.http.get<AnalyticsResponse>(`${API}/api/analytics/${shortCode}`);
  }
}
