//! Native macOS presentation and host-file transport for Standard File.

use std::ffi::{CStr, CString};
use std::fs;
use std::io;
use std::os::unix::ffi::OsStrExt;
use std::path::{Path, PathBuf};

use objc2_app_kit::{NSModalResponseOK, NSOpenPanel, NSSavePanel};
use objc2_foundation::{MainThreadMarker, NSString, NSURL};
use systemless::runner::VfsFileSnapshot;
use systemless::standard_file::StandardFileDialogRequest;

const RESOURCE_FORK_XATTR: &str = "com.apple.ResourceFork";
const FINDER_INFO_XATTR: &str = "com.apple.FinderInfo";
const APPLEDOUBLE_MAGIC: u32 = 0x0005_1607;
const APPLEDOUBLE_VERSION: u32 = 0x0002_0000;
const APPLEDOUBLE_RESOURCE_FORK: u32 = 2;
const APPLEDOUBLE_FINDER_INFO: u32 = 9;

pub fn run_dialog(request: &StandardFileDialogRequest) -> Option<PathBuf> {
    let mtm = MainThreadMarker::new().expect("file panels must run on the main thread");
    match request {
        StandardFileDialogRequest::Open { .. } => {
            let panel = unsafe { NSOpenPanel::openPanel(mtm) };
            unsafe {
                panel.setCanChooseFiles(true);
                panel.setCanChooseDirectories(false);
                panel.setAllowsMultipleSelection(false);
                panel.setResolvesAliases(true);
            }
            (unsafe { panel.runModal() } == NSModalResponseOK)
                .then(|| unsafe { panel.URL() })
                .flatten()
                .map(|url| url_path(&url))
        }
        StandardFileDialogRequest::Save {
            prompt,
            default_name,
        } => {
            let panel = unsafe { NSSavePanel::savePanel(mtm) };
            unsafe {
                panel.setCanCreateDirectories(true);
                panel.setNameFieldStringValue(&NSString::from_str(default_name));
                panel.setMessage(Some(&NSString::from_str(prompt)));
                panel.setPrompt(Some(&NSString::from_str("Save")));
            }
            (unsafe { panel.runModal() } == NSModalResponseOK)
                .then(|| unsafe { panel.URL() })
                .flatten()
                .map(|url| url_path(&url))
        }
    }
}

fn url_path(url: &NSURL) -> PathBuf {
    let bytes = unsafe { CStr::from_ptr(url.fileSystemRepresentation().as_ptr()) }.to_bytes();
    PathBuf::from(std::ffi::OsStr::from_bytes(bytes))
}

pub fn read_classic_file(path: &Path) -> io::Result<VfsFileSnapshot> {
    let data_fork = fs::read(path)?;
    let apple_double = read_apple_double(&apple_double_path(path)).unwrap_or_default();
    let resource_fork = read_xattr(path, RESOURCE_FORK_XATTR)?
        .or_else(|| apple_double.resource_fork.clone())
        .unwrap_or_default();
    let finder_info = read_xattr(path, FINDER_INFO_XATTR)?
        .or(apple_double.finder_info)
        .unwrap_or_default();
    let file_type = finder_info
        .get(0..4)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u32::from_be_bytes)
        .unwrap_or(u32::from_be_bytes(*b"????"));
    let creator = finder_info
        .get(4..8)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u32::from_be_bytes)
        .unwrap_or(u32::from_be_bytes(*b"????"));
    let finder_flags = finder_info
        .get(8..10)
        .and_then(|bytes| bytes.try_into().ok())
        .map(u16::from_be_bytes)
        .unwrap_or(0);
    let name = path
        .file_name()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "file has no name"))?
        .to_string_lossy()
        .into_owned();
    Ok(VfsFileSnapshot {
        path: name,
        data_fork,
        resource_fork,
        file_type,
        creator,
        finder_flags,
        created_date: 0,
        modified_date: 0,
    })
}

pub fn write_classic_file(path: &Path, file: &VfsFileSnapshot) -> io::Result<()> {
    fs::write(path, &file.data_fork)?;
    let finder_info = make_finder_info(file);
    let resource_result = if file.resource_fork.is_empty() {
        remove_xattr(path, RESOURCE_FORK_XATTR)
    } else {
        write_xattr(path, RESOURCE_FORK_XATTR, &file.resource_fork)
    };
    let finder_result = write_xattr(path, FINDER_INFO_XATTR, &finder_info);
    if resource_result.is_ok() && finder_result.is_ok() {
        return Ok(());
    }

    // Filesystems without native extended attributes use the standard
    // AppleDouble sidecar representation instead of discarding the resource
    // fork and Finder metadata.
    write_apple_double(&apple_double_path(path), &file.resource_fork, &finder_info)
}

fn make_finder_info(file: &VfsFileSnapshot) -> [u8; 32] {
    let mut info = [0; 32];
    info[0..4].copy_from_slice(&file.file_type.to_be_bytes());
    info[4..8].copy_from_slice(&file.creator.to_be_bytes());
    info[8..10].copy_from_slice(&file.finder_flags.to_be_bytes());
    info
}

fn path_cstring(path: &Path) -> io::Result<CString> {
    CString::new(path.as_os_str().as_bytes())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "path contains a NUL byte"))
}

fn read_xattr(path: &Path, name: &str) -> io::Result<Option<Vec<u8>>> {
    let path = path_cstring(path)?;
    let name = CString::new(name).unwrap();
    let size =
        unsafe { libc::getxattr(path.as_ptr(), name.as_ptr(), std::ptr::null_mut(), 0, 0, 0) };
    if size < 0 {
        let err = io::Error::last_os_error();
        return if xattr_is_absent_or_unsupported(&err) {
            Ok(None)
        } else {
            Err(err)
        };
    }
    let mut value = vec![0; size as usize];
    if size > 0 {
        let read = unsafe {
            libc::getxattr(
                path.as_ptr(),
                name.as_ptr(),
                value.as_mut_ptr().cast(),
                value.len(),
                0,
                0,
            )
        };
        if read < 0 {
            return Err(io::Error::last_os_error());
        }
        value.truncate(read as usize);
    }
    Ok(Some(value))
}

fn write_xattr(path: &Path, name: &str, value: &[u8]) -> io::Result<()> {
    let path = path_cstring(path)?;
    let name = CString::new(name).unwrap();
    let result = unsafe {
        libc::setxattr(
            path.as_ptr(),
            name.as_ptr(),
            value.as_ptr().cast(),
            value.len(),
            0,
            0,
        )
    };
    (result == 0)
        .then_some(())
        .ok_or_else(io::Error::last_os_error)
}

fn remove_xattr(path: &Path, name: &str) -> io::Result<()> {
    let path = path_cstring(path)?;
    let name = CString::new(name).unwrap();
    let result = unsafe { libc::removexattr(path.as_ptr(), name.as_ptr(), 0) };
    if result == 0 {
        return Ok(());
    }
    let err = io::Error::last_os_error();
    if xattr_is_absent_or_unsupported(&err) {
        Ok(())
    } else {
        Err(err)
    }
}

fn xattr_is_absent_or_unsupported(err: &io::Error) -> bool {
    matches!(
        err.raw_os_error(),
        Some(libc::ENOATTR) | Some(libc::ENOTSUP) | Some(libc::EOPNOTSUPP)
    )
}

#[derive(Default)]
struct AppleDouble {
    resource_fork: Option<Vec<u8>>,
    finder_info: Option<Vec<u8>>,
}

fn apple_double_path(path: &Path) -> PathBuf {
    let name = path
        .file_name()
        .map(|name| name.to_string_lossy())
        .unwrap_or_default();
    path.with_file_name(format!("._{name}"))
}

fn read_apple_double(path: &Path) -> io::Result<AppleDouble> {
    let bytes = fs::read(path)?;
    if read_be_u32(&bytes, 0) != Some(APPLEDOUBLE_MAGIC)
        || read_be_u32(&bytes, 4) != Some(APPLEDOUBLE_VERSION)
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid AppleDouble header",
        ));
    }
    let count = read_be_u16(&bytes, 24)
        .ok_or_else(|| io::Error::new(io::ErrorKind::UnexpectedEof, "short AppleDouble header"))?
        as usize;
    let mut result = AppleDouble::default();
    for index in 0..count {
        let entry = 26 + index * 12;
        let Some(id) = read_be_u32(&bytes, entry) else {
            break;
        };
        let Some(offset) = read_be_u32(&bytes, entry + 4).map(|value| value as usize) else {
            break;
        };
        let Some(length) = read_be_u32(&bytes, entry + 8).map(|value| value as usize) else {
            break;
        };
        let Some(value) = bytes.get(offset..offset.saturating_add(length)) else {
            continue;
        };
        match id {
            APPLEDOUBLE_RESOURCE_FORK => result.resource_fork = Some(value.to_vec()),
            APPLEDOUBLE_FINDER_INFO => result.finder_info = Some(value.to_vec()),
            _ => {}
        }
    }
    Ok(result)
}

fn write_apple_double(path: &Path, resource_fork: &[u8], finder_info: &[u8]) -> io::Result<()> {
    let entries = if resource_fork.is_empty() { 1 } else { 2 };
    let header_len = 26 + entries * 12;
    let mut bytes = Vec::with_capacity(header_len + finder_info.len() + resource_fork.len());
    bytes.extend_from_slice(&APPLEDOUBLE_MAGIC.to_be_bytes());
    bytes.extend_from_slice(&APPLEDOUBLE_VERSION.to_be_bytes());
    bytes.extend_from_slice(&[0; 16]);
    bytes.extend_from_slice(&(entries as u16).to_be_bytes());
    let finder_offset = header_len as u32;
    bytes.extend_from_slice(&APPLEDOUBLE_FINDER_INFO.to_be_bytes());
    bytes.extend_from_slice(&finder_offset.to_be_bytes());
    bytes.extend_from_slice(&(finder_info.len() as u32).to_be_bytes());
    if !resource_fork.is_empty() {
        let resource_offset = finder_offset + finder_info.len() as u32;
        bytes.extend_from_slice(&APPLEDOUBLE_RESOURCE_FORK.to_be_bytes());
        bytes.extend_from_slice(&resource_offset.to_be_bytes());
        bytes.extend_from_slice(&(resource_fork.len() as u32).to_be_bytes());
    }
    bytes.extend_from_slice(finder_info);
    bytes.extend_from_slice(resource_fork);
    fs::write(path, bytes)
}

fn read_be_u16(bytes: &[u8], offset: usize) -> Option<u16> {
    Some(u16::from_be_bytes(
        bytes.get(offset..offset + 2)?.try_into().ok()?,
    ))
}

fn read_be_u32(bytes: &[u8], offset: usize) -> Option<u32> {
    Some(u32::from_be_bytes(
        bytes.get(offset..offset + 4)?.try_into().ok()?,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn apple_double_round_trip_preserves_both_classic_entries() {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("._Document");
        let resource = b"resource fork";
        let finder = [0x5A; 32];
        write_apple_double(&path, resource, &finder).unwrap();
        let decoded = read_apple_double(&path).unwrap();
        assert_eq!(decoded.resource_fork.as_deref(), Some(resource.as_slice()));
        assert_eq!(decoded.finder_info.as_deref(), Some(finder.as_slice()));
    }
}
