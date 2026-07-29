//! Host-frontend bridge for the Classic Macintosh Standard File Package.
//!
//! The Toolbox implementation remains responsible for the guest-visible
//! reply records and virtual filesystem. A graphical frontend may replace
//! the emulated modal dialog with a native picker by taking one of these
//! requests and returning a response while the original `_Pack3` call is
//! suspended.

/// A modal file dialog requested by the guest Standard File Package.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum StandardFileDialogRequest {
    Open {
        /// Classic four-character file types accepted by the caller. `None`
        /// corresponds to the Standard File "all types" convention.
        allowed_file_types: Option<Vec<u32>>,
    },
    Save {
        prompt: String,
        default_name: String,
    },
}

/// Result supplied by a host frontend after presenting a native picker.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum StandardFileDialogResponse {
    Cancel,
    Open { name: String },
    Save { name: String },
}
