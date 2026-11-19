'use client';

import { createTheme } from '@mui/material/styles';

const fontFamily = [
  '"Be Vietnam Pro"',
  '"Inter"',
  '-apple-system',
  'BlinkMacSystemFont',
  '"Segoe UI"',
  '"Roboto"',
  'Arial',
  'sans-serif',
].join(',');

export const monoFontFamily = [
  '"JetBrains Mono"',
  'ui-monospace',
  'SFMono-Regular',
  'Menlo',
  'Consolas',
  'monospace',
].join(',');

// VinUni Brand Colors — Academic Light Design System
export const brandColors = {
  primary: '#0A2B57',       // VinUni Deep Navy
  primarySoft: '#EEF4FC',   // Soft Navy Tint
  accent: '#C72127',        // VinUni Signature Red
  accentSoft: '#FEF2F2',    // Soft Red Tint
  active: '#941616',        // Deep Crimson
  secondary: '#134D8B',     // Secondary Navy
  interactive: '#2599DC',   // Cyan Blue Focus/Link
  border: '#E5EAF0',        // Crisp 1px Structural Border
  borderStrong: '#CBD5E1',
  canvas: '#F6F8FB',        // Cool Light Slate Canvas
  surface: '#FFFFFF',
  subtle: '#F1F5F9',
};

export const statusColors = {
  // File status
  fileCompleted: { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6' },
  fileProcessing: { bg: '#EFF8FF', text: '#134D8B', border: '#B2DDFF' },
  fileNeedsReview: { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89' },
  fileError: { bg: '#FEF3F2', text: '#B42318', border: '#FECDCA' },

  // Matching status
  matchMeetsMandatory: { bg: '#EEF4FC', text: '#0A2B57', border: '#C7DDF7' },
  matchNeedsVerification: { bg: '#FFFAEB', text: '#B54708', border: '#FEDF89' },
  matchPossibleMismatch: { bg: '#FEF2F2', text: '#941616', border: '#FECACA' },

  // Application status
  appNew: { bg: '#F1F5F9', text: '#475569', border: '#E2E8F0' },
  appInReview: { bg: '#EFF8FF', text: '#175CD3', border: '#B2DDFF' },
  appShortlist: { bg: '#ECFDF3', text: '#067647', border: '#ABEFC6' },
  appRejected: { bg: '#FEF3F2', text: '#B42318', border: '#FECDCA' },
};

const theme = createTheme({
  palette: {
    primary: {
      main: brandColors.primary,
      dark: '#071E3D',
      light: '#1E4D82',
    },
    secondary: {
      main: brandColors.accent,
      dark: brandColors.active,
      light: '#E53935',
    },
    info: {
      main: brandColors.interactive,
    },
    success: {
      main: '#067647',
    },
    warning: {
      main: '#B54708',
    },
    error: {
      main: '#B42318',
    },
    background: {
      default: brandColors.canvas,
      paper: brandColors.surface,
    },
    text: {
      primary: '#0F172A',
      secondary: '#475569',
      disabled: '#94A3B8',
    },
    divider: brandColors.border,
  },
  typography: {
    fontFamily,
    h1: {
      fontSize: '26px',
      lineHeight: 1.25,
      fontWeight: 700,
      letterSpacing: '-0.02em',
    },
    h2: {
      fontSize: '20px',
      lineHeight: 1.3,
      fontWeight: 700,
      letterSpacing: '-0.015em',
    },
    h3: {
      fontSize: '17px',
      lineHeight: 1.35,
      fontWeight: 600,
      letterSpacing: '-0.01em',
    },
    h4: {
      fontSize: '15px',
      lineHeight: 1.4,
      fontWeight: 700,
    },
    h5: {
      fontSize: '18px',
      lineHeight: 1.35,
      fontWeight: 700,
      letterSpacing: '-0.01em',
    },
    h6: {
      fontSize: '15px',
      lineHeight: 1.4,
      fontWeight: 600,
    },
    body1: {
      fontSize: '14px',
      lineHeight: 1.5,
      fontWeight: 400,
    },
    body2: {
      fontSize: '13.5px',
      lineHeight: 1.5,
      fontWeight: 400,
    },
    caption: {
      fontSize: '12px',
      lineHeight: 1.4,
      fontWeight: 400,
      color: '#64748B',
    },
    overline: {
      fontSize: '11px',
      lineHeight: 1.3,
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.07em',
    },
    button: {
      fontSize: '13.5px',
      fontWeight: 600,
      textTransform: 'none',
      letterSpacing: '-0.005em',
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: brandColors.canvas,
          color: '#0F172A',
        },
      },
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          borderRadius: 12,
          border: `1px solid ${brandColors.border}`,
          backgroundColor: brandColors.surface,
          boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.02)',
          transition: 'border-color 0.16s ease, box-shadow 0.16s ease',
        },
      },
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          padding: 20,
          '&:last-child': {
            paddingBottom: 20,
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        outlined: {
          borderColor: brandColors.border,
          borderRadius: 12,
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 600,
          padding: '7px 14px',
          transition: 'background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, color 0.15s ease',
        },
        sizeSmall: {
          padding: '4px 11px',
          fontSize: '12.5px',
          borderRadius: 7,
        },
        sizeLarge: {
          padding: '10px 20px',
          fontSize: '14.5px',
          borderRadius: 9,
        },
        containedPrimary: {
          backgroundColor: brandColors.primary,
          '&:hover': {
            backgroundColor: '#071E3D',
            boxShadow: '0 2px 8px rgba(10, 43, 87, 0.22)',
          },
        },
        containedSecondary: {
          backgroundColor: brandColors.accent,
          '&:hover': {
            backgroundColor: brandColors.active,
            boxShadow: '0 2px 8px rgba(199, 33, 39, 0.24)',
          },
        },
        outlined: {
          borderColor: '#D5DEE9',
          backgroundColor: '#FFFFFF',
          '&:hover': {
            borderColor: '#94A3B8',
            backgroundColor: '#F8FAFC',
          },
        },
        outlinedPrimary: {
          borderColor: '#C5D4E8',
          color: brandColors.primary,
          '&:hover': {
            borderColor: brandColors.primary,
            backgroundColor: brandColors.primarySoft,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 7,
          fontWeight: 600,
          fontSize: '12px',
        },
        sizeSmall: {
          height: 24,
          fontSize: '11.5px',
        },
        outlined: {
          borderColor: brandColors.border,
          backgroundColor: '#FFFFFF',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
            backgroundColor: '#FFFFFF',
            '& fieldset': {
              borderColor: '#D5DEE9',
            },
            '&:hover fieldset': {
              borderColor: '#94A3B8',
            },
            '&.Mui-focused fieldset': {
              borderColor: brandColors.primary,
              borderWidth: 1.5,
            },
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: '#EDF2F7',
          fontVariantNumeric: 'tabular-nums',
        },
        head: {
          fontSize: '11.5px',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          color: '#64748B',
          backgroundColor: '#F8FAFC',
          borderBottom: `1px solid ${brandColors.border}`,
          paddingTop: 11,
          paddingBottom: 11,
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.12s ease',
          '&.MuiTableRow-hover:hover': {
            backgroundColor: '#F8FAFD',
          },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 42,
        },
        indicator: {
          height: 2.5,
          borderRadius: '2px 2px 0 0',
          backgroundColor: brandColors.accent,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          minHeight: 42,
          fontWeight: 600,
          fontSize: '13.5px',
          color: '#64748B',
          padding: '8px 16px',
          '&.Mui-selected': {
            color: brandColors.primary,
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 14,
          border: `1px solid ${brandColors.border}`,
          boxShadow: '0 20px 50px rgba(15, 23, 42, 0.14)',
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          fontSize: '17px',
          fontWeight: 700,
          color: '#0F172A',
          paddingBottom: 12,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          border: '1px solid transparent',
          fontSize: '13.5px',
        },
        standardInfo: {
          backgroundColor: '#F0F6FE',
          borderColor: '#C7DDF7',
          color: '#0A2B57',
        },
        standardWarning: {
          backgroundColor: '#FFFBEB',
          borderColor: '#FDE68A',
          color: '#92400E',
        },
        standardSuccess: {
          backgroundColor: '#ECFDF3',
          borderColor: '#ABEFC6',
          color: '#065F46',
        },
        standardError: {
          backgroundColor: '#FEF2F2',
          borderColor: '#FECACA',
          color: '#991B1B',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: '#0F172A',
          fontSize: '12px',
          borderRadius: 7,
          padding: '6px 10px',
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          backgroundColor: '#E5EAF0',
        },
        bar: {
          borderRadius: 999,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          color: '#0F172A',
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#FFFFFF',
          color: '#0F172A',
          borderRight: `1px solid ${brandColors.border}`,
        },
      },
    },
  },
});

export default theme;
