import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    objectName: "actiondrawServerDialog"
    property var server: null
    property var manager: null
    property var windowRoot: null
    property bool waitingForSave: false
    property var availableAddresses: []
    onOpened: {
        availableAddresses = server ? server.addresses : []
        network.currentIndex = 0
        for (var i = 0; i < availableAddresses.length; ++i) {
            if (server && availableAddresses[i].address === server.boundAddress)
                network.currentIndex = i
        }
    }
    title: server && server.running ? "ActionDraw Server" : "Start ActionDraw Server"
    modal: true
    width: Math.min(480, parent.width - 32)
    anchors.centerIn: parent
    standardButtons: Dialog.Close
    onClosed: waitingForSave = false

    function startServer() {
        if (!manager.currentFilePath) {
            waitingForSave = true
            windowRoot.performSave()
            return
        }
        if (server.prepare()) {
            var addresses = availableAddresses
            server.start(addresses[network.currentIndex].address, port.value)
        }
    }
    Connections {
        target: dialog.manager
        function onSaveCompleted(path) {
            if (dialog.waitingForSave && dialog.visible) {
                dialog.waitingForSave = false
                dialog.startServer()
            }
        }
    }
    contentItem: ColumnLayout {
        spacing: 12
        Label {
            text: "Open this project on your phone. Keep this computer awake and ActionDraw open. Both devices must be on Tailscale or another reachable private network."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        ComboBox {
            id: network
            Layout.fillWidth: true
            model: dialog.availableAddresses
            textRole: "label"
            enabled: dialog.server && !dialog.server.running
        }
        RowLayout {
            Label { text: "Port" }
            SpinBox { id: port; from: 1; to: 65535; value: 8765; editable: true; enabled: dialog.server && !dialog.server.running }
            Button { text: "Start Server"; visible: dialog.server && !dialog.server.running; onClicked: dialog.startServer() }
        }
        Label {
            text: dialog.server ? dialog.server.error : ""
            visible: text.length > 0
            color: "#f28c8c"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Rectangle {
            visible: dialog.server && dialog.server.running
            Layout.alignment: Qt.AlignHCenter
            width: 250; height: 250; color: "white"
            Image { anchors.fill: parent; anchors.margins: 8; source: dialog.server ? dialog.server.qr : ""; fillMode: Image.PreserveAspectFit }
        }
        TextField {
            visible: dialog.server && dialog.server.running
            Layout.fillWidth: true
            readOnly: true
            text: dialog.server ? dialog.server.url : ""
            selectByMouse: true
        }
        Label {
            visible: dialog.server && dialog.server.running
            text: "Open the link with http://, not https://. This server does not provide HTTPS; use Tailscale or another trusted private network. Anyone with this link can edit until you stop the server. Phone edits save automatically."
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        RowLayout {
            visible: dialog.server && dialog.server.running
            Button { text: "Copy Link"; onClicked: dialog.server.copyLink() }
            Button { text: "Stop Server"; onClicked: dialog.server.stop() }
        }
    }
}
