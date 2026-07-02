import { Routes } from '@angular/router';
import { UrlShortenerComponent } from './url-shortener/url-shortener.component';

export const routes: Routes = [
  { path: '', component: UrlShortenerComponent },
  { path: '**', redirectTo: '' }
];
