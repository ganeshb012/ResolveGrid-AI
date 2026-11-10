export type Language = 'en' | 'mr' | 'hi';

export interface Translations {
  appName: string;
  tagline: string;
  citizenPortal: string;
  adminDashboard: string;
  workerPortal: string;
  aiActivityCenter: string;
  reportIncident: string;
  myIncidents: string;
  liveStatus: string;
  voiceReport: string;
  textReport: string;
  recordAudio: string;
  recording: string;
  stopRecording: string;
  transcribingPrisma: string;
  submitComplaint: string;
  titlePlaceholder: string;
  descPlaceholder: string;
  category: string;
  priority: string;
  status: string;
  location: string;
  selectLocationOnMap: string;
  assignedWorker: string;
  listenStatusUpdate: string;
  voicePoweredTimbre: string;
  approvalsQueue: string;
  agentsActive: string;
  criticalAlert: string;
  accept: string;
  reject: string;
  markCompleted: string;
  uploadEvidence: string;
  resolutionNotes: string;
  login: string;
  register: string;
  logout: string;
  demoCredentials: string;
}

export const translations: Record<Language, Translations> = {
  en: {
    appName: "ResolveGrid AI",
    tagline: "Autonomous Multi-Agent Public Infrastructure Incident Platform",
    citizenPortal: "Citizen Portal",
    adminDashboard: "Operations Command",
    workerPortal: "Field Crew Hub",
    aiActivityCenter: "AI Multi-Agent Center",
    reportIncident: "Report Infrastructure Issue",
    myIncidents: "My Reported Incidents",
    liveStatus: "Real-time Tracking",
    voiceReport: "Voice Incident Reporting",
    textReport: "Text Reporting",
    recordAudio: "Tap to Speak (Marathi / Hindi / English)",
    recording: "Listening to your voice...",
    stopRecording: "Done Speaking",
    transcribingPrisma: "Transcribing with Gnani Prisma...",
    submitComplaint: "Submit Verified Complaint",
    titlePlaceholder: "Brief title (e.g. Broken water pipeline, Deep pothole)",
    descPlaceholder: "Describe the issue, landmarks, and severity in detail...",
    category: "Category",
    priority: "Priority",
    status: "Status",
    location: "Location",
    selectLocationOnMap: "Click map to set exact Pune coordinates",
    assignedWorker: "Assigned Field Crew",
    listenStatusUpdate: "Play Voice Update (Gnani Timbre)",
    voicePoweredTimbre: "Voice audio synthesized via Gnani Timbre",
    approvalsQueue: "Human Approval Queue",
    agentsActive: "5 Multi-Agent Swarm Active",
    criticalAlert: "Critical Incident Alert",
    accept: "Accept Task",
    reject: "Reject Task",
    markCompleted: "Complete & Request Verification",
    uploadEvidence: "Upload Photographic Proof",
    resolutionNotes: "Field Completion Notes",
    login: "Sign In",
    register: "Create Account",
    logout: "Sign Out",
    demoCredentials: "Quick Demo Credentials"
  },
  mr: {
    appName: "रिझॉल्व्हग्रीड एआय",
    tagline: "सार्वजनिक पायाभूत सुविधा निवारण प्रणाली",
    citizenPortal: "नागरिक पोर्टल",
    adminDashboard: "प्रशासकीय नियंत्रण कक्ष",
    workerPortal: "क्षेत्रीय कर्मचारी केंद्र",
    aiActivityCenter: "एआय मल्टी-एजंट केंद्र",
    reportIncident: "समस्या नोंदवा",
    myIncidents: "माझ्या तक्रारी",
    liveStatus: "थेट स्थिती ट्रॅकिंग",
    voiceReport: "आवाजाद्वारे तक्रार नोंदवा",
    textReport: "लिखित तक्रार",
    recordAudio: "बोलण्यासाठी स्पर्श करा (मराठी)",
    recording: "तुमचा आवाज ऐकत आहे...",
    stopRecording: "बोलणे पूर्ण झाले",
    transcribingPrisma: "ज्ञाणी प्रिझ्माद्वारे विश्लेषण...",
    submitComplaint: "तक्रार सादर करा",
    titlePlaceholder: "थोडक्यात शीर्षक (उदा. रस्त्यावरील खड्डा, पाण्याची गळती)",
    descPlaceholder: "समस्या आणि ठिकाणाचे सविस्तर वर्णन करा...",
    category: "प्रवर्ग",
    priority: "प्राधान्य",
    status: "स्थिती",
    location: "ठिकाण",
    selectLocationOnMap: "पुण्यातील अचूक ठिकाण निवडण्यासाठी नकाशावर क्लिक करा",
    assignedWorker: "नेमलेले कर्मचारी",
    listenStatusUpdate: "आवाज अद्यतन ऐका (ज्ञाणी टिंब्रे)",
    voicePoweredTimbre: "ज्ञाणी टिंब्रेद्वारे व्युत्पन्न आवाज",
    approvalsQueue: "मानवी मंजुरी रांग",
    agentsActive: "५ स्वायत्त एजंट सक्रिय",
    criticalAlert: "तातडीचा धोका इशारा",
    accept: "काम स्वीकारा",
    reject: "काम नाकारा",
    markCompleted: "काम पूर्ण करा आणि पडताळणी करा",
    uploadEvidence: "कामाचा फोटो अपलोड करा",
    resolutionNotes: "काम पूर्ण झाल्याची नोंद",
    login: "प्रवेश करा",
    register: "नोंदणी करा",
    logout: "बाहेर पडा",
    demoCredentials: "डेमो खाती"
  },
  hi: {
    appName: "रिज़ॉल्वग्रिड एआई",
    tagline: "स्वायत्त मल्टी-एजेंट नागरिक समस्या निवारण मंच",
    citizenPortal: "नागरिक पोर्टल",
    adminDashboard: "प्रशासन डैशबोर्ड",
    workerPortal: "कार्यकर्ता केंद्र",
    aiActivityCenter: "एआई मल्टी-एजेंट केंद्र",
    reportIncident: "समस्या दर्ज करें",
    myIncidents: "मेरी दर्ज शिकायतें",
    liveStatus: "लाइव स्थिति ट्रैकिंग",
    voiceReport: "आवाज़ से शिकायत दर्ज करें",
    textReport: "लिखित शिकायत",
    recordAudio: "बोलने के लिए दबाएं (हिंदी)",
    recording: "आपकी आवाज़ सुनी जा रही है...",
    stopRecording: "बोलना समाप्त",
    transcribingPrisma: "ज्ञानी प्रिज़्मा द्वारा ट्रांसक्राइब...",
    submitComplaint: "शिकायत सबमिट करें",
    titlePlaceholder: "संक्षिप्त शीर्षक (उदा. सड़क पर गड्ढा, पानी की पाइपलाइन)",
    descPlaceholder: "समस्या का विस्तृत विवरण और निकटतम स्थान दर्ज करें...",
    category: "श्रेणी",
    priority: "प्राथमिकता",
    status: "स्थिति",
    location: "स्थान",
    selectLocationOnMap: "पुणे में सटीक स्थान चुनने के लिए मानचित्र पर क्लिक करें",
    assignedWorker: "नियुक्त कार्यकर्ता",
    listenStatusUpdate: "आवाज़ अपडेट सुनें (ज्ञानी टिम्ब्रे)",
    voicePoweredTimbre: "ज्ञानी टिम्ब्रे द्वारा आवाज़ उत्पन्न",
    approvalsQueue: "मानव अनुमोदन कतार",
    agentsActive: "५ मल्टी-एजेंट सक्रिय",
    criticalAlert: "गंभीर समस्या चेतावनी",
    accept: "कार्य स्वीकारें",
    reject: "कार्य अस्वीकारें",
    markCompleted: "पूर्ण करें और सत्यापन भेजें",
    uploadEvidence: "फ़ोटो प्रमाण अपलोड करें",
    resolutionNotes: "कार्य समाप्ति टिप्पणी",
    login: "लॉग इन",
    register: "पंजीकरण",
    logout: "लॉग आउट",
    demoCredentials: "डेमो खाते"
  }
};
