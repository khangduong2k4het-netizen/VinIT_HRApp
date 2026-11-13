export const INTAKE_LIMITS = {
  maxFiles: 50,
  maxFileBytes: 10_000_000,
  maxBatchBytes: 250_000_000,
};

export interface IntakeFileLike {
  name: string;
  size: number;
}

export interface IntakeFileValidation {
  name: string;
  size: number;
  status: 'VALID' | 'WARNING' | 'INVALID';
  message: string;
}

export function validateIntakeFiles(files: IntakeFileLike[]) {
  const seenNames = new Map<string, number>();
  const duplicateNames = new Set<string>();
  files.forEach(file => {
    const key = file.name.trim().toLowerCase();
    const count = (seenNames.get(key) || 0) + 1;
    seenNames.set(key, count);
    if (count > 1) duplicateNames.add(key);
  });

  const items: IntakeFileValidation[] = files.map(file => {
    // F2.06: the backend OCRs JPG/PNG images, so the browser must not block them.
    if (!/\.(pdf|docx|jpe?g|png)$/i.test(file.name)) {
      return { name: file.name, size: file.size, status: 'INVALID', message: 'Chỉ hỗ trợ tệp PDF, DOCX, JPG hoặc PNG.' };
    }
    if (file.size === 0 || file.size > INTAKE_LIMITS.maxFileBytes) {
      return { name: file.name, size: file.size, status: 'INVALID', message: 'Mỗi tệp phải có dung lượng từ 1 byte đến 10 MB.' };
    }
    if (duplicateNames.has(file.name.trim().toLowerCase())) {
      return { name: file.name, size: file.size, status: 'WARNING', message: 'Tên tệp trùng trong lô; hãy kiểm tra trước khi gửi.' };
    }
    return { name: file.name, size: file.size, status: 'VALID', message: 'Sẵn sàng tải lên.' };
  });

  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  let batchError: string | null = null;
  if (files.length > INTAKE_LIMITS.maxFiles) batchError = 'Mỗi lô tối đa 50 tệp.';
  else if (totalBytes > INTAKE_LIMITS.maxBatchBytes) batchError = 'Tổng dung lượng lô không được vượt quá 250 MB.';
  else if (items.some(item => item.status === 'INVALID')) batchError = 'Một số tệp chưa hợp lệ. Hãy loại bỏ hoặc thay thế trước khi gửi.';

  return { items, batchError, totalBytes };
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_000_000) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1_000_000).toFixed(2)} MB`;
}
