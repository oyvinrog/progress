import QtQuick 2.15

Item {
    id: face

    property int level: 0
    property color fillColor: "#f4c95d"
    property color strokeColor: "#5b4515"

    onLevelChanged: canvas.requestPaint()
    onFillColorChanged: canvas.requestPaint()
    onStrokeColorChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()

            var size = Math.min(width, height)
            var centerX = width / 2
            var centerY = height / 2
            var radius = size * 0.46

            ctx.beginPath()
            ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
            ctx.fillStyle = face.fillColor
            ctx.fill()
            ctx.lineWidth = Math.max(1.5, size * 0.055)
            ctx.strokeStyle = face.strokeColor
            ctx.stroke()

            ctx.fillStyle = face.strokeColor
            ctx.beginPath()
            ctx.arc(centerX - size * 0.16, centerY - size * 0.12, size * 0.045, 0, Math.PI * 2)
            ctx.arc(centerX + size * 0.16, centerY - size * 0.12, size * 0.045, 0, Math.PI * 2)
            ctx.fill()

            var safeLevel = Math.max(0, Math.min(4, face.level))
            var endpointY = centerY + size * 0.17
            var controlOffsets = [-0.13, -0.06, 0.0, 0.10, 0.17]
            ctx.beginPath()
            ctx.moveTo(centerX - size * 0.20, endpointY)
            ctx.quadraticCurveTo(
                centerX,
                endpointY + size * controlOffsets[safeLevel],
                centerX + size * 0.20,
                endpointY
            )
            ctx.lineWidth = Math.max(1.8, size * 0.06)
            ctx.lineCap = "round"
            ctx.strokeStyle = face.strokeColor
            ctx.stroke()
        }
    }
}
