# NIA CRM Frontend

A React-based frontend for the NIA (AI Assistant) CRM Meeting Intelligence system.

## Features

- **Responsive Design**: Mobile-first design that works on all devices
- **Real-time Communication**: WebSocket integration for live updates
- **Meeting Calendar**: Interactive calendar with meeting intelligence overlays
- **AI-Powered Debriefing**: Real-time conversation interface with AI assistant
- **Lead Management**: Comprehensive lead tracking with meeting history
- **Competitive Intelligence**: Dashboard and reporting for competitive insights
- **Action Item Tracking**: Follow-up management with automated reminders
- **User Settings**: Calendar integration and notification preferences

## Technology Stack

- **React 18**: Modern React with hooks and functional components
- **Material-UI (MUI)**: Comprehensive UI component library
- **React Router**: Client-side routing
- **Socket.IO**: Real-time WebSocket communication
- **Axios**: HTTP client for API requests
- **React Calendar**: Interactive calendar component
- **Recharts**: Data visualization and charts
- **React Toastify**: Toast notifications
- **Formik & Yup**: Form handling and validation
- **Date-fns**: Date manipulation utilities

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Common/
│   │   │   ├── LoadingSpinner.js
│   │   │   └── ErrorBoundary.js
│   │   └── Layout/
│   │       ├── Layout.js
│   │       ├── NavigationItem.js
│   │       └── NotificationPanel.js
│   ├── contexts/
│   │   ├── AuthContext.js
│   │   └── WebSocketContext.js
│   ├── pages/
│   │   ├── Dashboard/
│   │   ├── MeetingCalendar/
│   │   ├── Debriefing/
│   │   ├── LeadManagement/
│   │   ├── CompetitiveIntelligence/
│   │   ├── ActionItems/
│   │   ├── Settings/
│   │   └── Login/
│   ├── App.js
│   ├── index.js
│   └── index.css
├── package.json
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Backend API server running on http://localhost:8000

### Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

The application will open at http://localhost:3000

### Environment Variables

The frontend uses a proxy configuration in package.json to connect to the backend API. For production, you may need to configure:

- `REACT_APP_API_URL`: Backend API URL
- `REACT_APP_WS_URL`: WebSocket server URL

## Available Scripts

- `npm start`: Start development server
- `npm build`: Build for production
- `npm test`: Run test suite
- `npm run eject`: Eject from Create React App (not recommended)

## Key Components

### Authentication
- JWT-based authentication with automatic token refresh
- Role-based access control (Admin, Sales Manager, Sales Rep, Viewer)
- Secure logout and session management

### Real-time Features
- WebSocket connection for live updates
- Real-time debriefing conversations
- Live notifications for meeting updates and CRM sync status
- Connection management with automatic reconnection

### Meeting Intelligence
- Interactive calendar with meeting detection indicators
- Meeting type classification and confidence scoring
- Participant matching with CRM leads
- Automated debriefing scheduling

### AI Debriefing
- Real-time conversation interface with AI assistant
- Context-aware questioning based on meeting type
- Structured data extraction preview
- Session management and recovery

### Data Management
- Comprehensive lead management with filtering and search
- Meeting history tracking and relationship progression
- Competitive intelligence dashboard with visualizations
- Action item tracking with priority and due date management

## Testing

The project includes unit tests for key components:

```bash
npm test
```

Test files are located in `__tests__` directories alongside components.

## Performance Optimizations

- Component lazy loading for large pages
- Efficient data fetching with pagination
- WebSocket connection pooling
- Optimized re-renders with React.memo and useMemo
- Image optimization and caching

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow the existing code style and patterns
2. Write unit tests for new components
3. Update documentation for new features
4. Test on multiple browsers and devices

## Security Considerations

- All API requests include authentication tokens
- Sensitive data is not stored in localStorage
- XSS protection through proper data sanitization
- CSRF protection through token validation
- Secure WebSocket connections with authentication

## Deployment

### Production Build

```bash
npm run build
```

This creates an optimized production build in the `build` folder.

### Docker Deployment

The frontend can be containerized and deployed with Docker:

```dockerfile
FROM node:16-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## API Integration

The frontend integrates with the Django REST API backend:

- Authentication: `/api/v1/auth/`
- Meetings: `/api/v1/meetings/`
- Debriefings: `/api/v1/debriefings/`
- Leads: `/api/v1/leads/`
- Action Items: `/api/v1/action-items/`
- Competitive Intelligence: `/api/v1/competitive-intelligence/`
- Analytics: `/api/v1/analytics/`

## WebSocket Events

Real-time communication handles these events:

- `notification`: General system notifications
- `meeting_update`: Meeting status changes
- `debriefing_reminder`: Debriefing reminders
- `crm_sync_status`: CRM synchronization updates
- `debriefing_message`: AI conversation messages
- `debriefing_complete`: Debriefing session completion

## Troubleshooting

### Common Issues

1. **API Connection Issues**: Check backend server status and proxy configuration
2. **WebSocket Connection Failures**: Verify WebSocket server is running and accessible
3. **Authentication Problems**: Clear browser storage and re-login
4. **Performance Issues**: Check for memory leaks and optimize component re-renders

### Debug Mode

Enable debug logging by setting:
```javascript
localStorage.setItem('debug', 'nia:*');
```

## License

This project is part of the NIA CRM Meeting Intelligence system.