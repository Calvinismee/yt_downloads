import React, { useState, useEffect, useRef } from 'react';

const DecryptedText = ({
  text = '',
  speed = 40,
  maxIterations = 7,
  characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()',
  className = '',
  parentClassName = '',
  encryptedClassName = '',
  animateOn = 'both',
  revealDirection = 'start',
}) => {
  const [displayText, setDisplayText] = useState(text);
  const [isDecrypting, setIsDecrypting] = useState(false);
  const elementRef = useRef(null);
  const animationFrameRef = useRef(null);
  const iterationCountRef = useRef(0);
  const revealedIndicesRef = useRef(new Set());

  const getRandomChar = () => {
    return characters[Math.floor(Math.random() * characters.length)];
  };

  const startDecryption = () => {
    if (isDecrypting) return;
    setIsDecrypting(true);
    iterationCountRef.current = 0;
    revealedIndicesRef.current.clear();
  };

  useEffect(() => {
    if (!isDecrypting) return;

    const animate = () => {
      const textLength = text.length;
      const revealedCount = revealedIndicesRef.current.size;

      if (revealedCount >= textLength) {
        setDisplayText(text);
        setIsDecrypting(false);
        return;
      }

      // Determine which characters to reveal based on direction
      if (iterationCountRef.current >= maxIterations) {
        // Reveal one more character
        let indexToReveal;
        if (revealDirection === 'center') {
          const mid = Math.floor(textLength / 2);
          const distance = Math.ceil((revealedCount + 1) / 2);
          indexToReveal = mid + (revealedCount % 2 === 0 ? distance : -distance);
          if (indexToReveal < 0 || indexToReveal >= textLength) {
            indexToReveal = revealedCount;
          }
        } else {
          indexToReveal = revealedCount;
        }

        if (indexToReveal < textLength) {
          revealedIndicesRef.current.add(indexToReveal);
        }
        iterationCountRef.current = 0;
      }

      // Update display text
      let newDisplayText = '';
      for (let i = 0; i < textLength; i++) {
        if (revealedIndicesRef.current.has(i)) {
          newDisplayText += text[i];
        } else {
          newDisplayText += getRandomChar();
        }
      }
      setDisplayText(newDisplayText);
      iterationCountRef.current++;

      animationFrameRef.current = setTimeout(animate, speed);
    };

    animate();

    return () => {
      if (animationFrameRef.current) {
        clearTimeout(animationFrameRef.current);
      }
    };
  }, [isDecrypting, text, speed, maxIterations, characters, revealDirection]);

  // Handle view-based animation
  useEffect(() => {
    if ((animateOn !== 'view' && animateOn !== 'both') || !elementRef.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          startDecryption();
          observer.unobserve(entry.target);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(elementRef.current);

    return () => observer.disconnect();
  }, [animateOn]);

  const handleMouseEnter = () => {
    if (animateOn === 'hover' || animateOn === 'both') {
      startDecryption();
    }
  };

  return (
    <span
      ref={elementRef}
      className={parentClassName}
      onMouseEnter={handleMouseEnter}
      style={{ cursor: (animateOn === 'hover' || animateOn === 'both') ? 'pointer' : 'default' }}
    >
      {displayText.split('').map((char, index) => (
        <span
          key={index}
          className={revealedIndicesRef.current.has(index) ? className : encryptedClassName}
        >
          {char}
        </span>
      ))}
    </span>
  );
};

export default DecryptedText;
