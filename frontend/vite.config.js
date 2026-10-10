import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()], server:{proxy:{'/review':'http://127.0.0.1:8000','/report':'http://127.0.0.1:8000','/reviews':'http://127.0.0.1:8000'}}});
