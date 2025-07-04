// Основные переменные
let mediaStream;
let websocket;
let currentMode = 'LIVE';
const FPS = 30;
let frameInterval;
let currentLanguage = 'ru'; // По умолчанию русский

// Словари переводов
const translations = {
    ru: {
        title: "Распознавание РЖЯ",
        startWebcam: "Включить камеру",
        stopWebcam: "Выключить камеру",
        startStream: "Запустить стрим",
        stopStream: "Остановить стрим",
        modeLabel: "Режим:",
        liveMode: "LIVE",
        trainingMode: "Тренировка",
        glossPlaceholder: "Введите жест",
        sendGloss: "Выбрать жест",
        webcamError: "Не удалось получить доступ к камере. Пожалуйста, проверьте разрешения.",
        wsConnected: "Соединение с сервером установлено",
        wsClosed: "Соединение с сервером закрыто",
        wsError: "Ошибка подключения к серверу",
        trainingActivated: "Режим тренировки активирован. Введите жест и нажмите \"Выбрать жест\"",
        liveActivated: "Режим LIVE активирован",
        glossRequired: "Пожалуйста, введите название жеста",
        glossSent: "Жест \"{gloss}\" отправлен на обучение. Пожалуйста, покажите его перед камерой",
        connectionError: "Соединение с сервером не установлено",
        correctGesture: "Правильно! Жест для \"{text}\" показан верно",
        languageChanged: "Язык изменен на русский. Инициализация модели..."
    },
    en: {
        title: "Sign Language Recognition",
        startWebcam: "Enable Camera",
        stopWebcam: "Disable Camera",
        startStream: "Start Stream",
        stopStream: "Stop Stream",
        modeLabel: "Mode:",
        liveMode: "LIVE",
        trainingMode: "Training",
        glossPlaceholder: "Enter gesture",
        sendGloss: "Select Gesture",
        webcamError: "Failed to access camera. Please check permissions.",
        wsConnected: "Connection to server established",
        wsClosed: "Connection to server closed",
        wsError: "Connection error",
        trainingActivated: "Training mode activated. Enter a gesture and click \"Select Gesture\"",
        liveActivated: "LIVE mode activated",
        glossRequired: "Please enter a gesture name",
        glossSent: "Gesture \"{gloss}\" sent for training. Please show it in front of the camera",
        connectionError: "Connection to server not established",
        correctGesture: "Correct! Gesture for \"{text}\" was shown correctly",
        languageChanged: "Language changed to English. Initializing model..."
    }
};

// Функция показа сообщения
function showMessage(textKey, type = 'success', data = {}) {
    let text = translations[currentLanguage][textKey] || textKey;

    // Заменяем плейсхолдеры
    text = text.replace('{text}', data.text || '');
    text = text.replace('{gloss}', data.gloss || '');

    const container = document.getElementById('messageContainer');
    const message = document.createElement('div');
    message.className = `message ${type}`;
    message.textContent = text;

    container.appendChild(message);

    // Анимация появления
    setTimeout(() => message.classList.add('show'), 10);

    // Автоматическое скрытие через 3 секунды
    setTimeout(() => {
        message.classList.remove('show');
        setTimeout(() => message.remove(), 300);
    }, 3000);
}

// Применение переводов
function applyTranslations() {
    const t = translations[currentLanguage];

    // Обновляем заголовок страницы
    document.title = t.title;

    // Обновляем элементы интерфейса
    document.getElementById('startWebcamButton').textContent = t.startWebcam;
    document.getElementById('stopWebcamButton').textContent = t.stopWebcam;
    document.getElementById('startStreamButton').textContent = t.startStream;
    document.getElementById('stopStreamButton').textContent = t.stopStream;
    document.getElementById('modeLabel').textContent = t.modeLabel;
    document.getElementById('liveModeBtn').textContent = t.liveMode;
    document.getElementById('trainingModeBtn').textContent = t.trainingMode;
    document.getElementById('gloss_text').placeholder = t.glossPlaceholder;
    document.getElementById('sendGlossButton').textContent = t.sendGloss;
}

// Отправка сообщения о смене языка на сервер
function sendLanguageToServer(lang) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const msg = {
            type: "LANGUAGE",
            lang: lang
        };
        websocket.send(JSON.stringify(msg));
        showMessage('languageChanged', 'info');
    } else {
        // Если WebSocket не открыт, сообщение будет отправлено при подключении
        showMessage('connectionError', 'error');
    }
}

// Сохраняем язык при переключении
function changeLanguage(lang) {
    // Если язык не изменился, ничего не делаем
    if (currentLanguage === lang) return;

    currentLanguage = lang;
    localStorage.setItem('slr_lang', lang);

    // Обновляем активную кнопку языка
    document.getElementById('langRu').classList.toggle('active', lang === 'ru');
    document.getElementById('langEn').classList.toggle('active', lang === 'en');

    // Применяем переводы интерфейса
    applyTranslations();

    // Отправляем сообщение на сервер
    sendLanguageToServer(lang);
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    // Инициализация языка
    const savedLang = localStorage.getItem('slr_lang');
    const browserLang = navigator.language.startsWith('ru') ? 'ru' : 'en';
    const lang = savedLang || browserLang;
    changeLanguage(lang);

    // Назначение обработчиков событий
    document.getElementById('startWebcamButton').addEventListener('click', startWebcam);
    document.getElementById('stopWebcamButton').addEventListener('click', stopWebcam);
    document.getElementById('startStreamButton').addEventListener('click', startStream);
    document.getElementById('stopStreamButton').addEventListener('click', stopStream);
    document.getElementById('liveModeBtn').addEventListener('click', () => switchMode('LIVE'));
    document.getElementById('trainingModeBtn').addEventListener('click', () => switchMode('TRAINING'));
    document.getElementById('sendGlossButton').addEventListener('click', sendGloss);
});

// Функции для работы с камерой и стримингом
function startWebcam() {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then((stream) => {
            const video = document.getElementById('webcam');
            video.srcObject = stream;
            mediaStream = stream;

            // Переключение видимости кнопок
            document.getElementById('startWebcamButton').classList.add('hidden');
            document.getElementById('stopWebcamButton').classList.remove('hidden');
            document.getElementById('streamControls').classList.remove('hidden');
        })
        .catch((error) => {
            console.error('Ошибка доступа к камере:', error);
            showMessage('webcamError', 'error');
        });
}

function stopWebcam() {
    if (mediaStream) {
        const tracks = mediaStream.getTracks();
        tracks.forEach(track => track.stop());

        const video = document.getElementById('webcam');
        video.srcObject = null;

        // Сброс интерфейса
        document.getElementById('startWebcamButton').classList.remove('hidden');
        document.getElementById('stopWebcamButton').classList.add('hidden');
        document.getElementById('streamControls').classList.add('hidden');
        document.getElementById('trainingControls').classList.add('hidden');

        // Остановка стрима если активен
        stopStream();
        if (frameInterval) {
            clearInterval(frameInterval);
            frameInterval = null;
        }
    }
}

function startStream() {
    // Переключение кнопок
    document.getElementById('startStreamButton').classList.add('hidden');
    document.getElementById('stopStreamButton').classList.remove('hidden');

    // Подключение к WebSocket
    websocket = new WebSocket('ws://localhost:3003/');

    websocket.onopen = () => {
        console.log('WebSocket подключен');
        showMessage('wsConnected', 'success');

        // Отправляем текущий язык при подключении
        sendLanguageToServer(currentLanguage);

        // Запускаем стриминг видео
        sendVideoStream();

        // Отправка текущего режима
        sendMode(currentMode);
    };

    websocket.onclose = () => {
        console.log('WebSocket отключен');
        showMessage('wsClosed', 'error');
        stopStream();
    };

    websocket.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
        showMessage('wsError', 'error');
    };

    websocket.onmessage = function(event) {
        console.log('Получено сообщение:', event.data);

        try {
            const data = JSON.parse(event.data);

            if (data.type === 'WORD') {
                // Получен ответ о правильном жесте
                showMessage('correctGesture', 'success', {text: data.text});
            }
        } catch (e) {
            console.error('Ошибка обработки сообщения:', e);
        }
    };
}

function stopStream() {
    document.getElementById('stopStreamButton').classList.add('hidden');
    document.getElementById('startStreamButton').classList.remove('hidden');
    document.getElementById('trainingControls').classList.add('hidden');

    if (frameInterval) {
        clearInterval(frameInterval);
        frameInterval = null;
    }

    if (websocket) {
        websocket.close();
        websocket = null;
    }
}

function switchMode(mode) {
    if (mode === currentMode) return;

    currentMode = mode;

    // Обновление UI
    document.getElementById('liveModeBtn').classList.toggle('active', mode === 'LIVE');
    document.getElementById('trainingModeBtn').classList.toggle('active', mode === 'TRAINING');

    // Показать/скрыть элементы тренировки
    if (mode === 'TRAINING') {
        document.getElementById('trainingControls').classList.remove('hidden');
        showMessage('trainingActivated', 'info');
    } else {
        document.getElementById('trainingControls').classList.add('hidden');
        showMessage('liveActivated', 'info');
    }

    // Отправка режима на сервер
    sendMode(mode);
}

function sendMode(mode) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const msg = {
            type: "MODE",
            mode: mode
        };
        websocket.send(JSON.stringify(msg));
    }
}

function sendGloss() {
    const glossInput = document.getElementById('gloss_text');
    const glossText = glossInput.value.trim();

    if (!glossText) {
        showMessage('glossRequired', 'error');
        return;
    }

    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const msg = {
            type: "GLOSS",
            gloss: glossText
        };
        websocket.send(JSON.stringify(msg));
        showMessage('glossSent', 'info', {gloss: glossText});
        glossInput.value = '';
    } else {
        showMessage('connectionError', 'error');
    }
}

function sendVideoStream() {
    const video = document.getElementById('webcam');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Установка размеров canvas
    const setCanvasSize = () => {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
    };

    // Первоначальная установка размеров
    setCanvasSize();

    // Обработчик изменения размеров видео
    video.addEventListener('resize', setCanvasSize);

    const sendFrame = () => {
        if (!video.videoWidth || !video.videoHeight) return;

        if (websocket && websocket.readyState === WebSocket.OPEN) {
            // Обновить размеры если изменились
            if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
                setCanvasSize();
            }

            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imageData = canvas.toDataURL('image/jpeg', 0.8);

            const msg = {
                type: "IMAGE",
                image: imageData,
                timestamp: Date.now()
            };

            websocket.send(JSON.stringify(msg));
        }
    };

    // Остановить предыдущий интервал если был
    if (frameInterval) {
        clearInterval(frameInterval);
    }

    frameInterval = setInterval(sendFrame, 1000 / FPS);
}
