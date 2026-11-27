'use client';

// Compact overflow menu to keep page headers calm (1 primary CTA + grouped secondary actions).
import * as React from 'react';
import { Button, ListItemIcon, ListItemText, Menu, MenuItem } from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import Link from 'next/link';

export interface OverflowActionItem {
  label: string;
  icon?: React.ReactNode;
  onClick?: () => void;
  href?: string;
  disabled?: boolean;
  hidden?: boolean;
}

interface Props {
  label: string;
  items: OverflowActionItem[];
}

export default function ActionOverflowMenu({ label, items }: Props) {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const visible = items.filter(item => !item.hidden);
  if (visible.length === 0) return null;

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        endIcon={<KeyboardArrowDownIcon />}
        onClick={event => setAnchorEl(event.currentTarget)}
        aria-haspopup="menu"
        aria-expanded={Boolean(anchorEl)}
      >
        {label}
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{ sx: { minWidth: 230, borderRadius: 2, mt: 0.5 } }}
      >
        {visible.map(item => (
          item.href ? (
            <MenuItem
              key={item.label}
              component={Link}
              href={item.href}
              disabled={item.disabled}
              onClick={() => setAnchorEl(null)}
            >
              {item.icon && <ListItemIcon>{item.icon}</ListItemIcon>}
              <ListItemText primary={item.label} primaryTypographyProps={{ variant: 'body2' }} />
            </MenuItem>
          ) : (
            <MenuItem
              key={item.label}
              disabled={item.disabled}
              onClick={() => {
                setAnchorEl(null);
                item.onClick?.();
              }}
            >
              {item.icon && <ListItemIcon>{item.icon}</ListItemIcon>}
              <ListItemText primary={item.label} primaryTypographyProps={{ variant: 'body2' }} />
            </MenuItem>
          )
        ))}
      </Menu>
    </>
  );
}
