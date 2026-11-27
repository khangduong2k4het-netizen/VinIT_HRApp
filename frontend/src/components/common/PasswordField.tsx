'use client';

import { useEffect, useRef, useState } from 'react';
import { IconButton, InputAdornment, TextField, TextFieldProps } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { useI18n } from '@/i18n/I18nProvider';

// A password input with a show/hide eye button. Hidden by default and hidden again when the form is submitted.
export default function PasswordField(props: Omit<TextFieldProps, 'type'>) {
  const { t } = useI18n();
  const [show, setShow] = useState(false);
  const holder = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const form = holder.current?.closest('form');
    if (!form) return;
    const hide = () => setShow(false);
    form.addEventListener('submit', hide);
    return () => form.removeEventListener('submit', hide);
  }, []);

  const label = show ? t('Ẩn mật khẩu') : t('Hiện mật khẩu');
  return (
    <TextField
      {...props}
      ref={holder}
      type={show ? 'text' : 'password'}
      InputProps={{
        ...props.InputProps,
        endAdornment: (
          <InputAdornment position="end">
            <IconButton
              edge="end"
              size="small"
              aria-label={label}
              aria-pressed={show}
              title={label}
              onClick={() => setShow(value => !value)}
              onMouseDown={event => event.preventDefault()}
            >
              {show ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
}
