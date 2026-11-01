import React, { useState } from 'react';
import { checkPhotoQuality, uploadPatientPhoto } from '../services/api';

export default function WoundPhotoUpload({ lang = 'en', onUploadSuccess, onOpenDischargePapers }) {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [checkingQuality, setCheckingQuality] = useState(false);
  const [qualityResult, setQualityResult] = useState(null);
  const [qualityError, setQualityError] = useState(null);
  const [patientNote, setPatientNote] = useState('');
  const [useAnyway, setUseAnyway] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(null);

  const isHindi = lang === 'hi';

  const handleFileChange = async (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    if (!selected.type.includes('jpeg') && !selected.type.includes('png') && !selected.type.includes('jpg')) {
      alert(isHindi ? 'कृपया केवल JPEG या PNG छवि चुनें।' : 'Please upload a JPEG or PNG image.');
      return;
    }

    if (selected.size > 8 * 1024 * 1024) {
      alert(isHindi ? 'छवि का आकार 8 MB से कम होना चाहिए।' : 'Image size must be under 8 MB.');
      return;
    }

    setFile(selected);
    const localUrl = URL.createObjectURL(selected);
    setPreviewUrl(localUrl);
    setQualityResult(null);
    setQualityError(null);
    setUseAnyway(false);
    setUploadSuccess(null);

    // Immediate deterministic quality check
    setCheckingQuality(true);
    const fd = new FormData();
    fd.append('file', selected);

    try {
      const qRes = await checkPhotoQuality(fd);
      setQualityResult(qRes);
    } catch (err) {
      setQualityError(err.message || (isHindi ? 'गुणवत्ता जांच में त्रुटि हुई।' : 'Quality check failed.'));
    } finally {
      setCheckingQuality(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setPreviewUrl(null);
    setQualityResult(null);
    setQualityError(null);
    setUseAnyway(false);
    setPatientNote('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    if (patientNote.trim()) {
      fd.append('patient_note', patientNote.trim());
    }
    if (useAnyway) {
      fd.append('use_anyway', 'true');
    }

    try {
      const res = await uploadPatientPhoto(fd);
      setUploadSuccess(res);
      if (onUploadSuccess) onUploadSuccess(res);
    } catch (err) {
      alert(err.message || (isHindi ? 'फोटो अपलोड विफल रहा।' : 'Photo upload failed.'));
    } finally {
      setUploading(false);
    }
  };

  // SUCCESS CONFIRMATION STATE (F4 Copy Lock)
  if (uploadSuccess) {
    return (
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid #bbf7d0',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: '#ecfdf5',
              color: '#047857',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px',
            }}
          >
            ✓
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: '#047857' }}>
              {isHindi ? 'फोटो सफलतापूर्वक प्राप्त हुई' : 'Photo received'}
            </h4>
            <div style={{ fontSize: '11px', color: '#64748b' }}>
              SHA-256: <code>{uploadSuccess.sha256?.slice(0, 16)}...</code> · Status: <strong>{uploadSuccess.quality_status}</strong>
            </div>
          </div>
        </div>

        {/* F4 Required Confirmation Copy */}
        <div
          style={{
            background: 'var(--bg-base, #f8fafc)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '8px',
            padding: '14px 16px',
            fontSize: '13px',
            lineHeight: 1.5,
            color: 'var(--text-primary, #0f172a)',
          }}
        >
          {isHindi
            ? 'फोटो प्राप्त हो गई है। हमारी नर्सिंग टीम इसकी समीक्षा करेगी। हम स्वचालित रूप से चिकित्सा जांच नहीं करते हैं। यदि आप चिंतित हैं, तो दैनिक चेक-इन का उपयोग करें या अपनी देखभाल टीम से संपर्क करें।'
            : 'Photo received. A nurse will look at it. We do not check it automatically. If you are worried, use your daily check-in or call your care team.'}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', justifyContent: 'space-between' }}>
          <button
            type="button"
            onClick={() => {
              if (onOpenDischargePapers) onOpenDischargePapers();
              else alert('Warning signs from discharge papers: severe tightness, shortness of breath, redness spreading beyond 2 inches, or fever > 100.4°F.');
            }}
            style={{
              padding: '7px 14px',
              borderRadius: '6px',
              border: '1px solid #cbd5e1',
              background: 'var(--bg-surface, #ffffff)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            📄 {isHindi ? 'अपने डिस्चार्ज पेपर से चेतावनी संकेत देखें' : 'See warning signs from your papers'}
          </button>

          <button
            type="button"
            onClick={handleReset}
            style={{
              padding: '7px 14px',
              borderRadius: '6px',
              border: 'none',
              background: 'var(--navy-deep, #0b1528)',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {isHindi ? 'एक और फोटो भेजें' : 'Submit another photo'}
          </button>
        </div>

        <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '10px', fontSize: '11px', color: '#dc2626', fontWeight: 600 }}>
          🚨 {isHindi ? 'गंभीर या आपातकालीन लक्षणों के मामले में तुरंत 112 पर कॉल करें।' : 'For severe symptoms or emergencies, call 112 immediately.'}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'var(--bg-surface, #ffffff)',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: '12px',
        padding: '20px 24px',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <div style={{ marginBottom: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
            📷 {isHindi ? 'घाव या चीरे की फोटो अपलोड करें' : 'Recovery & Wound Photo Check-in'}
          </h3>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
            {isHindi
              ? 'चीरे की स्पष्ट फोटो लें। आपकी नर्स इसकी समीक्षा करेगी। गोपनीयता के लिए स्थान और EXIF डेटा हटा दिया जाता है।'
              : 'Add a clear photo of your healing incision. A nurse will review it. Location and EXIF metadata are removed.'}
          </p>
        </div>
      </div>

      {!file ? (
        <label
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '32px 20px',
            border: '2px dashed var(--border-strong, #cbd5e1)',
            borderRadius: '10px',
            background: 'var(--bg-base, #f8fafc)',
            cursor: 'pointer',
            textAlign: 'center',
            gap: '8px',
          }}
        >
          <div style={{ fontSize: '32px' }}>📸</div>
          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            {isHindi ? 'फोटो चुनें या कैमरे से लें' : 'Take photo or choose from library'}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b' }}>
            JPEG, PNG · {isHindi ? 'अधिकतम 8 MB · 640px न्यूनतम' : 'Up to 8 MB · Minimum 640px'}
          </div>
          <input
            type="file"
            accept="image/jpeg,image/png,image/jpg"
            capture="environment"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
        </label>
      ) : (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Photo Preview & Quality Result Badge */}
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', width: '180px', height: '180px', borderRadius: '10px', overflow: 'hidden', border: '1px solid #cbd5e1', background: '#000' }}>
              <img
                src={previewUrl}
                alt="Wound preview"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
              <button
                type="button"
                onClick={handleReset}
                title={isHindi ? 'फोटो हटाएं' : 'Remove photo'}
                style={{
                  position: 'absolute',
                  top: '6px',
                  right: '6px',
                  background: 'rgba(0,0,0,0.6)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '50%',
                  width: '24px',
                  height: '24px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                ✕
              </button>
            </div>

            {/* Quality Feedback Card */}
            <div style={{ flex: 1, minWidth: '240px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
                {isHindi ? 'स्वचालित गुणवत्ता जांच' : 'Automated Quality Check'}
              </div>

              {checkingQuality ? (
                <div style={{ fontSize: '12px', color: '#64748b', padding: '10px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px' }}>
                  ⏳ {isHindi ? 'गुणवत्ता जांची जा रही है...' : 'Evaluating sharpness, lighting, and resolution...'}
                </div>
              ) : qualityResult ? (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    background: qualityResult.is_usable ? '#ecfdf5' : '#fffbeb',
                    border: qualityResult.is_usable ? '1px solid #a7f3d0' : '1px solid #fde68a',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '16px' }}>{qualityResult.is_usable ? '✓' : '⚠️'}</span>
                    <strong style={{ fontSize: '13px', color: qualityResult.is_usable ? '#047857' : '#b45309' }}>
                      {qualityResult.message}
                    </strong>
                  </div>

                  {qualityResult.details && (
                    <div style={{ fontSize: '11px', color: qualityResult.is_usable ? '#065f46' : '#92400e' }}>
                      {qualityResult.details}
                    </div>
                  )}

                  {qualityResult.metrics && (
                    <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px', display: 'flex', gap: '10px' }}>
                      <span>Size: {qualityResult.metrics.width}×{qualityResult.metrics.height}</span>
                      <span>Light: {qualityResult.metrics.brightness}/255</span>
                      <span>Sharpness: {qualityResult.metrics.sharpness}</span>
                    </div>
                  )}
                </div>
              ) : qualityError ? (
                <div style={{ fontSize: '12px', color: '#dc2626', padding: '8px', background: '#fef2f2', borderRadius: '6px' }}>
                  ❌ {qualityError}
                </div>
              ) : null}

              {/* Retake vs Use Anyway Toggle if quality check flagged issues */}
              {qualityResult && !qualityResult.is_usable && (
                <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <button
                    type="button"
                    onClick={handleReset}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #cbd5e1',
                      background: 'var(--bg-surface, #ffffff)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      alignSelf: 'flex-start',
                    }}
                  >
                    ↻ {isHindi ? 'पुनः फोटो लें' : 'Retake photo with better lighting/focus'}
                  </button>

                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#475569', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={useAnyway}
                      onChange={(e) => setUseAnyway(e.target.checked)}
                    />
                    <span>{isHindi ? 'फिर भी यह फोटो उपयोग करें (Use anyway)' : 'Use this photo anyway'}</span>
                  </label>
                </div>
              )}
            </div>
          </div>

          {/* Optional Patient Note */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#64748b', marginBottom: '4px', textTransform: 'uppercase' }}>
              {isHindi ? 'चीरे या रिकवरी पर कोई टिप्पणी (वैकल्पिक)' : 'Notes on incision or healing area (optional)'}
            </label>
            <input
              type="text"
              maxLength={250}
              placeholder={isHindi ? 'उदा. ऊपरी किनारे पर हल्का खिंचाव, कोई बुखार नहीं' : 'e.g. Mild redness around suture edge, no drainage'}
              value={patientNote}
              onChange={(e) => setPatientNote(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                background: 'var(--bg-base, #ffffff)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '12px',
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: '8px 14px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                background: 'transparent',
                color: 'var(--text-secondary, #475569)',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              {isHindi ? 'रद्द करें' : 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={uploading || checkingQuality || (!qualityResult?.is_usable && !useAnyway)}
              style={{
                padding: '8px 18px',
                borderRadius: '6px',
                border: 'none',
                background: 'var(--navy-deep, #0b1528)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 700,
                cursor: (uploading || checkingQuality || (!qualityResult?.is_usable && !useAnyway)) ? 'not-allowed' : 'pointer',
                opacity: (uploading || checkingQuality || (!qualityResult?.is_usable && !useAnyway)) ? 0.6 : 1,
              }}
            >
              {uploading ? (isHindi ? 'भेजा जा रहा है...' : 'Sending photo...') : (isHindi ? 'देखभाल टीम को भेजें' : 'Send Photo to Care Team')}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
